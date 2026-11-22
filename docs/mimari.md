# Proje Mimarisi

Verinin kaynaktan dashboard'a kadar izledigi yol. Her kutunun altinda ureten script ve sorumlu kisi yazar.

![Mimari sema](mimari.png)

```mermaid
flowchart LR
    subgraph K["Veri kaynagi"]
        TLC["NYC TLC<br/>Yellow Taxi<br/>Ocak-Mart 2026<br/>11,08 M satir"]
        ZONE["taxi_zone_lookup.csv<br/>265 bolge"]
    end

    subgraph V["1. Kisi: Veri hazirlama"]
        RAW[("data/raw/<br/>ham Parquet")]
        TEMIZ["temizle.py<br/>PySpark<br/>8 kural + zone join"]
        PROC[("data/processed/<br/>temiz Parquet + CSV<br/>10,45 M satir")]
        SAMP[("data/samples/<br/>1ay / 2ay / 3ay")]
    end

    subgraph A["Analiz"]
        AGG["aggregations.py<br/>PySpark<br/>groupBy, join, window, SQL<br/><i>2. Kisi</i>"]
        BENCH["benchmark_*.py<br/>pandas vs Spark<br/>CSV vs Parquet<br/><i>3. Kisi</i>"]
        ML["model_egit.py<br/>scikit-learn<br/>sure tahmini<br/><i>3. Kisi</i>"]
    end

    subgraph S["Sonuclar (kucuk dosyalar)"]
        RES[("results/agg/*.csv<br/>results/*.csv<br/>docs/*.md")]
    end

    DASH["dashboard/app.py<br/>Streamlit + Plotly<br/>6 sekme<br/><i>2. Kisi</i>"]

    TLC -->|veri_indir.py| RAW
    ZONE --> TEMIZ
    RAW --> TEMIZ --> PROC
    PROC -->|orneklem_olustur.py| SAMP
    PROC --> AGG
    PROC --> ML
    SAMP --> BENCH
    ZONE --> AGG
    AGG --> RES
    BENCH --> RES
    ML --> RES
    TEMIZ -->|temizlik raporu| RES
    RES --> DASH
```

## Katmanlar

| Katman | Teknoloji | Neden |
|---|---|---|
| Depolama | Parquet (ZSTD / Snappy) | Sutun bazli: sadece gereken sutunlar okunur, CSV'den ~6,7 kat kucuk |
| Isleme | PySpark (yerel mod, `local[*]`) | Veri bellege sigmasa da parca parca isler; ayni kod kumeye tasinabilir |
| Karsilastirma | pandas | Tek makinede klasik yaklasim; benchmark'ta referans |
| Model | scikit-learn | Yolculuk suresi tahmini |
| Sunum | Streamlit + Plotly | Hazir sonuc dosyalarini okur, Spark gerektirmez, aninda acilir |

**Hesaplama ve gorsellestirme ayri.** Agir isler (temizlik, aggregation, benchmark, model) bir kez calisip kucuk sonuc
dosyalari uretir. Dashboard yalnizca bu dosyalari okur. Boylece 10 milyon satiri her etkilesimde yeniden islemek gerekmez.
