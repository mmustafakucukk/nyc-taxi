# Yolculuk suresi (trip_duration_min) tahmini icin regresyon modelleri egitir ve karsilastirir.
#
# Soru: Yolcu taksiye bindigi anda bilinen bilgilerle yolculugun kac dakika surecegini tahmin edebilir miyiz?
#
# Egitim / test ayrimi zamana gore:
#   Egitim: Ocak + Subat 2026   (model bu aylardan ogrenir)
#   Test:   Mart 2026           (model hic gormedigi bir ayda sinanir)
#
# Uc model:
#   1) Baseline (taban cizgi): her yolculuk icin egitim verisinin ortalama suresini soyler
#   2) Linear Regression: mesafe + saat + gun + ilce ile dogrusal bir formul
#   3) HistGradientBoosting: karar agaclarindan olusan guclu bir model
#
# Metrikler: MAE, RMSE, R2
#
# Ciktilar:
#   results/model_sonuclari.csv
#   results/model_grafik.png
#   docs/model_raporu.md
#
# Kullanim: python src/model_egit.py  (once src/temizle.py calismis olmali)

import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import TargetEncoder

KAYNAK = "data/processed/parquet"
EGITIM_AYLARI = ["2026-01", "2026-02"]
TEST_AYI = "2026-03"
HEDEF = "trip_duration_min"

# Sadece yolcu taksiye bindigi anda BILINEN bilgiler kullaniliyor.
# Kullanilmayanlar ve nedenleri (veri sizintisi / data leakage):
#   tpep_dropoff_datetime : inis zamani, sureyi dogrudan verir
#   avg_speed_mph         : mesafe / sure ile hesaplandi, icinde cevap var
#   fare_amount, total_amount, tip_amount : taksimetre ucreti sureye gore artiyor, yolculuk bitince belli olur
OZELLIKLER = [
    "trip_distance", "PULocationID", "DOLocationID", "PU_Borough", "DO_Borough",
    "pickup_hour", "pickup_dayofweek", "RatecodeID", "VendorID",
]

ILCE_TIPI = pd.CategoricalDtype(
    sorted(pd.read_csv("data/raw/taxi_zone_lookup.csv")["Borough"].dropna().unique())
)


def oku(aylar):
    parcalar = [pd.read_parquet(f"{KAYNAK}/yellow_temiz_{ay}.parquet", columns=OZELLIKLER + [HEDEF])
                for ay in aylar]
    return pd.concat(parcalar, ignore_index=True)


def metrikler(gercek, tahmin):
    return {
        "MAE": mean_absolute_error(gercek, tahmin),
        "RMSE": np.sqrt(mean_squared_error(gercek, tahmin)),
        "R2": r2_score(gercek, tahmin),
    }


# ---- Model 2 icin ozellikler: Linear Regression ----
def dogrusal_ozellikler(df, sutunlar=None):
    # Dogrusal model "saat 18" ile "saat 9"u sayi olarak gorurse 18'in 2 kat etkisi var sanar.
    # Bu yuzden saat, gun ve ilceyi one-hot encoding ile 0/1 sutunlarina ceviriyoruz:
    #   pickup_hour = 18  ->  saat_18 = 1, diger saat sutunlari = 0
    X = pd.get_dummies(
        df[["pickup_hour", "pickup_dayofweek", "PU_Borough", "DO_Borough"]].astype(str),
        prefix=["saat", "gun", "PU", "DO"], dtype="float32",
    )
    X["trip_distance"] = df["trip_distance"].astype("float32")
    if sutunlar is not None:
        # Test verisinde egitimde olmayan bir kategori varsa 0 olarak eklenir, sutun sirasi ayni olur
        X = X.reindex(columns=sutunlar, fill_value=0)
    return X


# ---- Model 3 icin ozellikler: HistGradientBoosting ----
def agac_ozellikleri(df, kodlayici, egitim=False):
    X = df[["trip_distance", "pickup_hour", "pickup_dayofweek", "RatecodeID", "VendorID"]].copy()
    # Ilce sadece birkac farkli deger: agac modeline dogrudan kategori olarak veriyoruz.
    # Kategori listesi sabit: egitim ve testte "Manhattan" ayni koda karsilik gelmeli.
    for s in ["PU_Borough", "DO_Borough"]:
        X[s] = df[s].astype(ILCE_TIPI)
    # 263 bolge (zone) cok fazla kategori. Target encoding ile her bolgeyi,
    # egitim verisinde o bolgeden baslayan/biten yolculuklarin ortalama suresiyle temsil ediyoruz.
    # fit_transform egitimde capraz dogrulama (cross fitting) yapar: bir satirin kodu
    # kendi suresi kullanilmadan hesaplanir, boylece sizinti olmaz.
    bolgeler = df[["PULocationID", "DOLocationID"]]
    if egitim:
        kod = kodlayici.fit_transform(bolgeler, df[HEDEF])
    else:
        kod = kodlayici.transform(bolgeler)
    X["PU_bolge_kodu"] = kod[:, 0]
    X["DO_bolge_kodu"] = kod[:, 1]
    return X


def grafik_ciz(y_test, tahminler, onem):
    fig, eksen = plt.subplots(1, 3, figsize=(17, 4.8))

    # 1) Gercek - tahmin: noktalar kosegene ne kadar yakinsa model o kadar iyi
    hb = eksen[0].hexbin(y_test, tahminler["HistGradientBoosting"], gridsize=60, bins="log",
                         extent=(0, 90, 0, 90), cmap="viridis")
    eksen[0].plot([0, 90], [0, 90], "r--", lw=1)
    eksen[0].set_title("HistGradientBoosting: gercek vs tahmin (Mart)")
    eksen[0].set_xlabel("gercek sure (dk)")
    eksen[0].set_ylabel("tahmin (dk)")
    fig.colorbar(hb, ax=eksen[0], label="yolculuk sayisi (log)")

    # 2) Modellerin MAE degeri
    adlar = list(tahminler)
    mae = [mean_absolute_error(y_test, tahminler[a]) for a in adlar]
    etiketler = ["Baseline", "Linear\nRegression", "HistGradient\nBoosting"]
    cubuk = eksen[1].bar(etiketler, mae, color=["#999999", "#4C72B0", "#55A868"])
    eksen[1].bar_label(cubuk, fmt="%.2f dk")
    eksen[1].set_title("Ortalama mutlak hata (MAE) - dusuk iyi")
    eksen[1].set_ylabel("dakika")

    # 3) Hangi ozellik ne kadar onemli
    onem = onem.sort_values()
    eksen[2].barh(onem.index, onem.values, color="#55A868")
    eksen[2].set_title("Ozellik onemi (permutation importance)")
    eksen[2].set_xlabel("karistirilinca R2'deki dusus")

    fig.tight_layout()
    fig.savefig("results/model_grafik.png", dpi=120)


def rapor_yaz(sonuclar, onem, egitim_n, test_n, y_test, tahmin_hgb):
    r = ["# Yolculuk Suresi Tahmin Modeli\n"]
    r.append("**Soru:** Yolcu taksiye bindigi anda bilinen bilgilerle yolculugun kac dakika surecegi "
             "tahmin edilebilir mi?\n")
    r.append(f"- Hedef: `{HEDEF}` (dakika)")
    r.append(f"- Egitim: {' + '.join(EGITIM_AYLARI)} ({egitim_n:,} yolculuk)")
    r.append(f"- Test: {TEST_AYI} ({test_n:,} yolculuk). Model bu ayi egitimde hic gormedi.")
    r.append(f"- Ozellikler: {', '.join(OZELLIKLER)}")
    r.append("- Kullanilmayanlar (veri sizintisi): inis zamani, ortalama hiz, ucret / toplam / bahsis. "
             "Bunlar yolculuk bitince belli olur ve sureyi dolayli olarak icerir.\n")

    r.append("## Sonuclar (Mart test verisi)\n")
    r.append("| Model | MAE (dk) | RMSE (dk) | R2 | Egitim suresi (sn) |")
    r.append("|---|---|---|---|---|")
    for s in sonuclar:
        r.append(f"| {s['model']} | {s['MAE']:.2f} | {s['RMSE']:.2f} | {s['R2']:.3f} | {s['egitim_sn']:.1f} |")

    r.append("\n## Ozellik onemi\n")
    r.append("Bir ozelligin degerleri rastgele karistirildiginda modelin R2 degeri ne kadar dusuyor? "
             "Cok dusuyorsa model o ozellige cok guveniyor demektir. (Test verisinden 200 bin satirlik "
             "orneklem, 3 tekrar.)\n")
    r.append("| Ozellik | R2 dususu |")
    r.append("|---|---|")
    for ad, deger in onem.sort_values(ascending=False).items():
        r.append(f"| {ad} | {deger:.3f} |")

    r.append("\n## Hata, yolculuk uzunluguna gore (HistGradientBoosting)\n")
    r.append("| Gercek sure | Yolculuk | MAE (dk) |")
    r.append("|---|---|---|")
    dilim = pd.cut(y_test, [0, 10, 20, 40, 60, 180], labels=["0-10 dk", "10-20 dk", "20-40 dk", "40-60 dk", "60+ dk"])
    hata = pd.DataFrame({"dilim": dilim, "hata": np.abs(y_test - tahmin_hgb)})
    for d, g in hata.groupby("dilim", observed=True):
        r.append(f"| {d} | {len(g):,} | {g['hata'].mean():.2f} |")

    r.append("\n![grafikler](../results/model_grafik.png)\n")
    with open("docs/model_raporu.md", "w", encoding="utf-8") as f:
        f.write("\n".join(r))


if __name__ == "__main__":
    baslangic = time.time()
    egitim = oku(EGITIM_AYLARI)
    test = oku([TEST_AYI])
    y_egitim, y_test = egitim[HEDEF].to_numpy(), test[HEDEF].to_numpy()
    print(f"egitim: {len(egitim):,} satir, test: {len(test):,} satir")

    sonuclar, tahminler = [], {}

    def kaydet(ad, tahmin, egitim_sn):
        m = metrikler(y_test, tahmin)
        sonuclar.append({"model": ad, **m, "egitim_sn": egitim_sn})
        tahminler[ad] = tahmin
        print(f"{ad:<22} MAE {m['MAE']:.2f} dk  RMSE {m['RMSE']:.2f} dk  R2 {m['R2']:.3f}  ({egitim_sn:.1f} sn)")

    # ---- 1) Baseline ----
    # Hicbir ozellige bakmadan "her yolculuk ortalama X dakika surer" diyen model.
    # Diger modellerin gercekten bir sey ogrenip ogrenmedigini anlamak icin karsilastirma noktasi.
    kaydet("Baseline (ortalama)", np.full(len(test), y_egitim.mean()), 0.0)

    # ---- 2) Linear Regression ----
    X_egitim = dogrusal_ozellikler(egitim)
    X_test = dogrusal_ozellikler(test, X_egitim.columns)
    bas = time.perf_counter()
    dogrusal = LinearRegression().fit(X_egitim, y_egitim)
    sure = time.perf_counter() - bas
    kaydet("Linear Regression", dogrusal.predict(X_test), sure)
    del X_egitim, X_test

    # ---- 3) HistGradientBoosting ----
    # cv: kodlar 5 parcaya bolunerek hesaplanir (cross fitting), shuffle + random_state ile her seferinde ayni bolme
    kodlayici = TargetEncoder(target_type="continuous", cv=KFold(5, shuffle=True, random_state=42))
    X_egitim = agac_ozellikleri(egitim, kodlayici, egitim=True)
    X_test = agac_ozellikleri(test, kodlayici)
    bas = time.perf_counter()
    agac = HistGradientBoostingRegressor(
        max_iter=300,          # en fazla 300 agac
        learning_rate=0.1,     # her yeni agac oncekilerin hatasinin %10'unu duzeltir
        max_leaf_nodes=63,     # her agac en fazla 63 yaprak
        categorical_features="from_dtype",  # category tipindeki sutunlar (ilceler) kategori olarak islenir
        random_state=42,
    ).fit(X_egitim, y_egitim)
    sure = time.perf_counter() - bas
    tahmin_hgb = agac.predict(X_test)
    kaydet("HistGradientBoosting", tahmin_hgb, sure)
    print(f"  kullanilan agac sayisi: {agac.n_iter_} / 300")

    # ---- Ozellik onemi ----
    orneklem = X_test.sample(200_000, random_state=42)
    onem_sonuc = permutation_importance(agac, orneklem, y_test[orneklem.index], scoring="r2",
                                        n_repeats=3, random_state=42, n_jobs=1)
    onem = pd.Series(onem_sonuc.importances_mean, index=orneklem.columns)

    pd.DataFrame(sonuclar).to_csv("results/model_sonuclari.csv", index=False)
    grafik_ciz(y_test, tahminler, onem)
    rapor_yaz(sonuclar, onem, len(egitim), len(test), y_test, tahmin_hgb)
    print(f"\nbitti, toplam {time.time() - baslangic:.0f} sn. Rapor: docs/model_raporu.md")
