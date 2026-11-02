"""Small stack smoke test; writes each run beneath the selected tools root."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from importlib.metadata import version
from urllib.request import urlretrieve

import duckdb


def _sql_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def new_run_directory(tools_root: Path) -> Path:
    """Create a unique run directory without touching earlier smoke artifacts."""
    tools_root = tools_root.expanduser().resolve()
    tools_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="smoke-", dir=tools_root))


def delta_classpath(root: Path) -> str:
    """Download the pinned Delta runtime outside Spark's temporary directory."""
    delta_version = version("delta-spark")
    if delta_version != "3.3.2":
        raise RuntimeError("Update the smoke test JAR dependencies for this delta-spark version")
    artifacts = (
        ("io/delta/delta-spark_2.12", f"delta-spark_2.12-{delta_version}.jar"),
        ("io/delta/delta-storage", f"delta-storage-{delta_version}.jar"),
        ("org/antlr/antlr4-runtime", "antlr4-runtime-4.9.3.jar"),
    )
    jars = root / "jars"
    jars.mkdir()
    paths = []
    for group, name in artifacts:
        path = jars / name
        artifact_version = "4.9.3" if group.startswith("org/antlr/") else delta_version
        urlretrieve(f"https://repo.maven.apache.org/maven2/{group}/{artifact_version}/{name}", path)
        paths.append(str(path.resolve()))
    return os.pathsep.join(paths)


def main() -> None:
    # Import the optional Spark runtime only for the actual integration run.
    from delta.tables import DeltaTable
    from pyspark.sql import SparkSession

    tools_root = Path(os.environ.get("BDSRE_TOOLS_ROOT", ".tools"))
    # Spark may hold JARs open on Windows; each run is isolated and no earlier
    # smoke artifact is deleted.
    root = new_run_directory(tools_root)

    db = duckdb.connect()
    try:
        ext_dir = root / "duckdb-extensions"
        db.execute(f"SET extension_directory='{_sql_path(ext_dir)}'")
        db.execute("INSTALL tpch")
        db.execute("LOAD tpch")
        db.execute("CALL dbgen(sf=0.001)")
        rows = db.execute("SELECT count(*) FROM lineitem").fetchone()[0]
        assert rows == 6005, rows
    finally:
        db.close()

    classpath = delta_classpath(root)
    builder = (
        SparkSession.builder.master("local[2]")
        .appName("BDSRE-stack-smoke")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.driver.extraClassPath", classpath)
        .config("spark.executor.extraClassPath", classpath)
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.databricks.delta.snapshotPartitions", "2")
        .config("spark.databricks.delta.optimize.maxFileSize", "1048576")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    try:
        table_path = (root / "delta-table").as_posix()
        for i in range(4):
            (
                spark.range(i * 100, (i + 1) * 100)
                .selectExpr("id", "id % 10 AS group_id")
                .coalesce(1)
                .write.format("delta")
                .mode("append")
                .save(table_path)
            )
        table = DeltaTable.forPath(spark, table_path)

        def summary() -> tuple[int, int, int]:
            frame = spark.read.format("delta").load(table_path)
            return (
                frame.count(),
                frame.selectExpr("sum(id) AS total").first().total,
                len(frame.inputFiles()),
            )

        before = summary()
        table.optimize().executeCompaction()
        compacted = summary()
        table.optimize().executeZOrderBy("group_id", "id")
        zordered = summary()
        assert before[:2] == compacted[:2] == zordered[:2] == (400, 79800)
        assert compacted[2] < before[2], (before, compacted)
        print(f"TPC-H rows={rows}; files: {before[2]} -> {compacted[2]} -> {zordered[2]}")
        print(f"Smoke-test artifacts kept at: {root}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
