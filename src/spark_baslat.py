# Tum scriptlerde ayni ayarlarla Spark baslatmak icin.
# Kullanim:
#   from spark_baslat import spark_olustur
#   spark = spark_olustur("uygulama_adi")

import glob
import os
import sys

# Windows'ta birden fazla Python kuruluysa Spark yanlis olani acip cokuyor.
# Spark'a su an calisan Python'u (venv) kullanmasini soyluyoruz.
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession


def spark_olustur(uygulama_adi, bellek="6g"):
    spark = (
        SparkSession.builder
        .master("local[*]")  # bilgisayardaki tum cekirdekleri kullan
        .appName(uygulama_adi)
        .config("spark.driver.memory", bellek)
        .config("spark.sql.session.timeZone", "America/New_York")
        .config("spark.ui.showConsoleProgress", "false")  # [Stage 1: ===> ] cubugunu gizle
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")  # ekrani WARN mesajlariyla doldurmasin
    return spark


def ham_dosyalar():
    # Spark'a "data/raw/*.parquet" verirsek Windows'ta winutils.exe olmadigi icin takiliyor.
    # Bu yuzden dosya listesini Python'un glob'u ile cikarip Spark'a tek tek veriyoruz:
    #   spark.read.parquet(*ham_dosyalar())
    return sorted(glob.glob("data/raw/yellow_tripdata_*.parquet"))
