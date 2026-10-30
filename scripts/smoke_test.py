"""Small stack smoke test; keeps generated files under the selected tools root."""
import os
from pathlib import Path
import shutil

import duckdb
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession
from delta.tables import DeltaTable

root = Path(os.environ.get("BDSRE_TOOLS_ROOT", ".tools")) / "smoke"
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
db = duckdb.connect()
ext_dir = root / "duckdb-extensions"
db.execute(f"SET extension_directory='{ext_dir.as_posix()}'")
db.execute("INSTALL tpch")
db.execute("LOAD tpch")
db.execute("CALL dbgen(sf=0.001)")
rows = db.execute("SELECT count(*) FROM lineitem").fetchone()[0]
assert rows == 6005, rows

builder = (SparkSession.builder.master("local[2]").appName("BDSRE-stack-smoke")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .config("spark.jars.ivy", (root / "ivy").as_posix())
    .config("spark.sql.shuffle.partitions", "2")
    .config("spark.databricks.delta.snapshotPartitions", "2")
    .config("spark.databricks.delta.optimize.maxFileSize", "1048576"))
spark = configure_spark_with_delta_pip(builder).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
try:
    table_path = (root / "delta-table").as_posix()
    for i in range(4):
        (spark.range(i * 100, (i + 1) * 100)
         .selectExpr("id", "id % 10 AS group_id").coalesce(1)
         .write.format("delta").mode("append").save(table_path))
    table = DeltaTable.forPath(spark, table_path)
    def summary():
        frame = spark.read.format("delta").load(table_path)
        return (frame.count(), frame.selectExpr("sum(id) AS total").first().total,
                len(frame.inputFiles()))
    before = summary()
    table.optimize().executeCompaction()
    compacted = summary()
    table.optimize().executeZOrderBy("group_id", "id")
    zordered = summary()
    assert before[:2] == compacted[:2] == zordered[:2] == (400, 79800)
    assert compacted[2] < before[2], (before, compacted)
    print(f"TPC-H rows={rows}; files: {before[2]} -> {compacted[2]} -> {zordered[2]}")
finally:
    spark.stop()
