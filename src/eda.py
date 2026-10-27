"""Phân tích sơ bộ (EDA) bộ dữ liệu Default of Credit Card Clients (UCI #350).

Chạy:  python src/eda.py
Đầu ra: reports/figures/*.png và reports/tables/*.csv
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "default of credit card clients.xls"
FIG = ROOT / "reports" / "figures"
TAB = ROOT / "reports" / "tables"
FIG.mkdir(parents=True, exist_ok=True)
TAB.mkdir(parents=True, exist_ok=True)

TARGET = "default"
PAY = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
BILL = [f"BILL_AMT{i}" for i in range(1, 7)]
PAYAMT = [f"PAY_AMT{i}" for i in range(1, 7)]
MONTHS = ["T9", "T8", "T7", "T6", "T5", "T4"]  # cột 1 = tháng 9/2005 ... cột 6 = tháng 4/2005
CLASS_NAMES = {0: "Không vỡ nợ", 1: "Vỡ nợ"}
PALETTE = {"Không vỡ nợ": "#4C72B0", "Vỡ nợ": "#DD5555"}

sns.set_theme(style="whitegrid", font="DejaVu Sans")
plt.rcParams["figure.dpi"] = 120


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, bbox_inches="tight")
    plt.close(fig)


def load():
    df = pd.read_excel(DATA, header=1).rename(columns={"default payment next month": TARGET})
    df["Lớp"] = df[TARGET].map(CLASS_NAMES)
    return df


def overview(df):
    feats = df.drop(columns=["ID", TARGET, "Lớp"])
    info = {
        "so_mau": len(df),
        "so_dac_trung": feats.shape[1],
        "gia_tri_thieu": int(df.isna().sum().sum()),
        "dong_trung_lap_bo_ID": int(df.drop(columns="ID").duplicated().sum()),
        "so_vo_no": int(df[TARGET].sum()),
        "ty_le_vo_no": round(df[TARGET].mean(), 4),
        "EDUCATION_ma_la_0_5_6": int(df["EDUCATION"].isin([0, 5, 6]).sum()),
        "MARRIAGE_ma_la_0": int((df["MARRIAGE"] == 0).sum()),
        "BILL_AMT_am_it_nhat_1_thang": int((df[BILL] < 0).any(axis=1).sum()),
        "BILL_AMT_bang_0_ca_6_thang": int((df[BILL] == 0).all(axis=1).sum()),
    }
    pd.Series(info).to_csv(TAB / "00_tong_quan.csv", header=["gia_tri"])

    desc = feats.describe().T
    desc["skew"] = feats.skew()
    desc.round(2).to_csv(TAB / "01_thong_ke_mo_ta.csv")
    return info


def overview_figure(df, info):
    """Hình tổng quan: các con số chính và cơ cấu nhãn."""
    fig = plt.figure(figsize=(12, 3.6))
    cards = [
        (f"{info['so_mau']:,}".replace(",", "."), "khách hàng"),
        (str(info["so_dac_trung"]), "đặc trưng đầu vào"),
        ("6 tháng", "lịch sử (4–9/2005)"),
        ("0", "giá trị thiếu"),
    ]
    for i, (value, label) in enumerate(cards):
        ax = fig.add_axes([0.01 + i * 0.165, 0.12, 0.15, 0.76])
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, color="#EEF2F8", transform=ax.transAxes))
        ax.text(0.5, 0.58, value, ha="center", va="center", fontsize=24, weight="bold", color="#2F4B7C")
        ax.text(0.5, 0.25, label, ha="center", va="center", fontsize=11, color="#444444")
        ax.axis("off")

    ax = fig.add_axes([0.68, 0.02, 0.3, 0.96])
    counts = df["Lớp"].value_counts().reindex(CLASS_NAMES.values())
    ax.pie(counts, colors=[PALETTE[c] for c in counts.index], startangle=90, counterclock=False,
           wedgeprops=dict(width=0.38, edgecolor="white"))
    ax.text(0, 0.08, f"{df[TARGET].mean():.1%}".replace(".", ","), ha="center", fontsize=18,
            weight="bold", color=PALETTE["Vỡ nợ"])
    ax.text(0, -0.18, "vỡ nợ", ha="center", fontsize=11)
    ax.legend([f"{c}: {n:,}".replace(",", ".") for c, n in counts.items()],
              loc="center left", bbox_to_anchor=(0.92, 0.5), frameon=False, fontsize=10)
    fig.savefig(FIG / "00_tong_quan_du_lieu.png", bbox_inches="tight")
    plt.close(fig)


def structure_figure():
    """Sơ đồ cấu trúc một mẫu: thông tin tĩnh + 3 chuỗi 6 tháng -> nhãn tháng 10."""
    fig, ax = plt.subplots(figsize=(12, 4.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4.6)
    ax.axis("off")

    def box(x, y, w, h, text, color, size=10):
        ax.add_patch(plt.Rectangle((x, y), w, h, facecolor=color, edgecolor="white", lw=2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size)

    box(0, 0.4, 2.4, 3.4, "Thông tin tĩnh\n\nLIMIT_BAL\nSEX\nEDUCATION\nMARRIAGE\nAGE", "#E3E8F0")
    months = ["T4", "T5", "T6", "T7", "T8", "T9"]
    rows = [("Trạng thái trả nợ", ["PAY_6", "PAY_5", "PAY_4", "PAY_3", "PAY_2", "PAY_0"], "#F6D5D5"),
            ("Dư nợ sao kê", [f"BILL_AMT{i}" for i in range(6, 0, -1)], "#D9E6F2"),
            ("Số tiền đã trả", [f"PAY_AMT{i}" for i in range(6, 0, -1)], "#DCEFD9")]
    for j, m in enumerate(months):
        ax.text(3.0 + j * 1.15 + 0.55, 4.2, m + "/2005", ha="center", fontsize=10, weight="bold")
    for r, (name, cols, color) in enumerate(rows):
        y = 2.85 - r * 1.2
        ax.text(2.95, y + 0.85, name, fontsize=9.5, style="italic", color="#333333")
        for j, c in enumerate(cols):
            box(3.0 + j * 1.15, y, 1.1, 0.75, c, color, size=8.5)
    ax.annotate("", xy=(10.3, 2.1), xytext=(9.95, 2.1), arrowprops=dict(arrowstyle="-|>", lw=2, color="#555555"))
    box(10.4, 1.35, 1.6, 1.5, "Nhãn\nT10/2005\n\nVỡ nợ: 1\nKhông: 0", "#F2C4C4")
    fig.savefig(FIG / "00b_cau_truc_du_lieu.png", bbox_inches="tight")
    plt.close(fig)


def target_distribution(df):
    counts = df["Lớp"].value_counts().reindex(CLASS_NAMES.values())
    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(counts.index, counts.values, color=[PALETTE[c] for c in counts.index])
    for b, v in zip(bars, counts.values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,}\n({v / len(df):.1%})", ha="center", va="bottom")
    ax.set_ylabel("Số khách hàng")
    ax.set_title("Phân bố nhãn (tháng 10/2005)")
    ax.set_ylim(0, counts.max() * 1.18)
    save(fig, "01_phan_bo_nhan.png")


def categorical(df):
    """Tỷ lệ vỡ nợ theo nhóm và kiểm định Chi-square độc lập với nhãn."""
    labels = {
        "SEX": {1: "Nam", 2: "Nữ"},
        "EDUCATION": {0: "0 (lạ)", 1: "Sau ĐH", 2: "Đại học", 3: "THPT", 4: "Khác", 5: "5 (lạ)", 6: "6 (lạ)"},
        "MARRIAGE": {0: "0 (lạ)", 1: "Đã kết hôn", 2: "Độc thân", 3: "Khác"},
    }
    rows = []
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, (col, mp) in zip(axes, labels.items()):
        g = df.groupby(col)[TARGET].agg(["count", "mean"]).rename(index=mp)
        ax.bar(g.index.astype(str), g["mean"], color="#DD5555")
        for i, (n, r) in enumerate(zip(g["count"], g["mean"])):
            ax.text(i, r, f"{r:.1%}\nn={n:,}", ha="center", va="bottom", fontsize=8)
        ax.axhline(df[TARGET].mean(), ls="--", c="gray", lw=1)
        ax.set_title(f"Tỷ lệ vỡ nợ theo {col}")
        ax.set_ylim(0, g["mean"].max() * 1.3)
        ax.tick_params(axis="x", rotation=30)
        chi2, p, *_ = stats.chi2_contingency(pd.crosstab(df[col], df[TARGET]))
        rows.append({"dac_trung": col, "chi2": round(chi2, 2), "p_value": p})
        g.assign(dac_trung=col).to_csv(TAB / f"02_ty_le_vo_no_{col}.csv")
    save(fig, "02_ty_le_vo_no_nhan_khau.png")
    return pd.DataFrame(rows)


def pay_status(df):
    rate = df.groupby("PAY_0")[TARGET].agg(["count", "mean"])
    rate.to_csv(TAB / "03_ty_le_vo_no_PAY_0.csv")

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
    ax = axes[0]
    ax.bar(rate.index.astype(str), rate["mean"], color="#DD5555")
    for i, (n, r) in enumerate(zip(rate["count"], rate["mean"])):
        ax.text(i, r, f"{r:.0%}\nn={n:,}", ha="center", va="bottom", fontsize=8)
    ax.axhline(df[TARGET].mean(), ls="--", c="gray", lw=1, label="Trung bình toàn bộ")
    ax.set_xlabel("PAY_0 (trạng thái trả nợ tháng 9: -2, -1, 0 = không trễ; k = trễ k tháng)")
    ax.set_ylabel("Tỷ lệ vỡ nợ")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.set_title("Tỷ lệ vỡ nợ theo trạng thái trả nợ tháng gần nhất")

    # Số tháng có trễ hạn (giá trị > 0) trong 6 tháng
    late = (df[PAY] > 0).sum(axis=1)
    g = df.groupby(late)[TARGET].agg(["count", "mean"])
    ax = axes[1]
    ax.bar(g.index.astype(str), g["mean"], color="#C44E52")
    for i, (n, r) in enumerate(zip(g["count"], g["mean"])):
        ax.text(i, r, f"{r:.0%}\nn={n:,}", ha="center", va="bottom", fontsize=8)
    ax.set_xlabel("Số tháng trễ hạn trong 6 tháng (T4–T9/2005)")
    ax.set_ylabel("Tỷ lệ vỡ nợ")
    ax.set_ylim(0, 1.05)
    ax.set_title("Tỷ lệ vỡ nợ theo số tháng trễ hạn")
    save(fig, "03_trang_thai_tra_no.png")
    g.to_csv(TAB / "03b_ty_le_vo_no_so_thang_tre.csv")


def numeric_by_class(df):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    sns.histplot(data=df, x="LIMIT_BAL", hue="Lớp", stat="density", common_norm=False,
                 bins=50, element="step", palette=PALETTE, ax=axes[0])
    axes[0].set_title("Phân bố hạn mức tín dụng (LIMIT_BAL, NT$)")
    sns.histplot(data=df, x="AGE", hue="Lớp", stat="density", common_norm=False,
                 bins=range(20, 80, 2), element="step", palette=PALETTE, ax=axes[1])
    axes[1].set_title("Phân bố tuổi (AGE)")
    save(fig, "04_han_muc_tuoi_theo_lop.png")

    # Tỷ lệ vỡ nợ theo nhóm tuổi và nhóm hạn mức
    age_bin = pd.cut(df["AGE"], [20, 25, 30, 35, 40, 45, 50, 60, 80], right=False)
    lim_bin = pd.qcut(df["LIMIT_BAL"], 5)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    for ax, b, title in [(axes[0], age_bin, "nhóm tuổi"), (axes[1], lim_bin, "ngũ phân vị hạn mức")]:
        g = df.groupby(b, observed=True)[TARGET].mean()
        ax.bar(g.index.astype(str), g.values, color="#DD5555")
        ax.axhline(df[TARGET].mean(), ls="--", c="gray", lw=1)
        ax.set_title(f"Tỷ lệ vỡ nợ theo {title}")
        ax.tick_params(axis="x", rotation=30)
    save(fig, "05_ty_le_vo_no_tuoi_han_muc.png")

    # Kiểm định Mann–Whitney U cho các biến liên tục (phân phối lệch, không chuẩn)
    rows = []
    for col in ["LIMIT_BAL", "AGE"] + BILL + PAYAMT:
        a, b = df.loc[df[TARGET] == 0, col], df.loc[df[TARGET] == 1, col]
        u, p = stats.mannwhitneyu(a, b)
        rows.append({"dac_trung": col, "trung_vi_khong_vo_no": a.median(),
                     "trung_vi_vo_no": b.median(), "p_value": p})
    pd.DataFrame(rows).to_csv(TAB / "04_mann_whitney.csv", index=False)


def monthly_trends(df):
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))
    for ax, cols, title in [(axes[0], PAY, "Trạng thái trả nợ TB"),
                            (axes[1], BILL, "Dư nợ sao kê TB (NT$)"),
                            (axes[2], PAYAMT, "Số tiền đã trả TB (NT$)")]:
        m = df.groupby("Lớp")[cols].mean()
        for cls, row in m.iterrows():
            ax.plot(MONTHS[::-1], row.values[::-1], marker="o", label=cls, color=PALETTE[cls])
        ax.set_title(title)
        ax.legend()
    save(fig, "06_xu_huong_6_thang.png")


def correlation(df):
    feats = df.drop(columns=["ID", "Lớp"])
    corr = feats.corr(method="spearman")
    fig, ax = plt.subplots(figsize=(13, 11))
    sns.heatmap(corr, cmap="RdBu_r", center=0, vmin=-1, vmax=1, square=True,
                cbar_kws={"shrink": 0.7}, ax=ax)
    ax.set_title("Ma trận tương quan Spearman")
    save(fig, "07_tuong_quan.png")

    with_target = corr[TARGET].drop(TARGET).sort_values(key=abs, ascending=False)
    with_target.round(4).to_csv(TAB / "05_tuong_quan_voi_nhan.csv", header=["spearman"])
    fig, ax = plt.subplots(figsize=(7, 6))
    colors = ["#DD5555" if v > 0 else "#4C72B0" for v in with_target.values]
    ax.barh(with_target.index[::-1], with_target.values[::-1], color=colors[::-1])
    ax.set_title("Tương quan Spearman của từng đặc trưng với nhãn")
    save(fig, "08_tuong_quan_voi_nhan.png")

    # Đo mức đa cộng tuyến trong nhóm BILL_AMT
    corr.loc[BILL, BILL].round(3).to_csv(TAB / "06_tuong_quan_BILL_AMT.csv")


def projection(df):
    """Chiếu dữ liệu xuống không gian thấp chiều để nhìn mức chồng lấn giữa 2 lớp."""
    X = StandardScaler().fit_transform(df.drop(columns=["ID", TARGET, "Lớp"]))
    y = df[TARGET].values
    pca = PCA().fit(X)
    Z = pca.transform(X)[:, :2]
    lda = LinearDiscriminantAnalysis(n_components=1).fit(X, y)
    z_lda = lda.transform(X).ravel()

    rng = np.random.default_rng(42)
    idx = rng.choice(len(df), 6000, replace=False)
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.5))
    for cls in (0, 1):
        m = y[idx] == cls
        axes[0].scatter(Z[idx][m, 0], Z[idx][m, 1], s=4, alpha=0.4,
                        color=PALETTE[CLASS_NAMES[cls]], label=CLASS_NAMES[cls])
    axes[0].set_xlim(np.percentile(Z[:, 0], [0.5, 99.5]))
    axes[0].set_ylim(np.percentile(Z[:, 1], [0.5, 99.5]))
    axes[0].set_title("PCA 2 chiều (mẫu 6.000 điểm)")
    axes[0].set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%})")
    axes[0].set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%})")
    axes[0].legend(markerscale=4)

    cum = np.cumsum(pca.explained_variance_ratio_)
    axes[1].plot(range(1, len(cum) + 1), cum, marker="o")
    axes[1].axhline(0.9, ls="--", c="gray")
    axes[1].set_title("Phương sai tích luỹ của PCA")
    axes[1].set_xlabel("Số thành phần chính")

    for cls in (0, 1):
        sns.kdeplot(z_lda[y == cls], ax=axes[2], fill=True, color=PALETTE[CLASS_NAMES[cls]],
                    label=CLASS_NAMES[cls], clip=np.percentile(z_lda, [0.5, 99.5]))
    axes[2].set_title("Chiếu Fisher LDA 1 chiều")
    axes[2].legend()
    save(fig, "09_pca_lda.png")

    pd.Series({"so_TP_dat_90pct_phuong_sai": int(np.argmax(cum >= 0.9) + 1),
               "PC1": pca.explained_variance_ratio_[0], "PC2": pca.explained_variance_ratio_[1]}
              ).to_csv(TAB / "07_pca.csv", header=["gia_tri"])


def utilization(df):
    """Xem trước đặc trưng phái sinh: tỷ lệ sử dụng hạn mức tháng 9."""
    util = (df["BILL_AMT1"] / df["LIMIT_BAL"]).clip(-0.5, 1.5)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    sns.histplot(x=util, hue=df["Lớp"], stat="density", common_norm=False, bins=60,
                 element="step", palette=PALETTE, ax=ax)
    ax.set_xlabel("BILL_AMT1 / LIMIT_BAL")
    ax.set_title("Tỷ lệ sử dụng hạn mức tháng 9")
    save(fig, "10_ty_le_su_dung_han_muc.png")
    g = df.groupby(pd.cut(util, [-0.5, 0, 0.25, 0.5, 0.75, 1.0, 1.5]), observed=True)[TARGET].agg(["count", "mean"])
    g.to_csv(TAB / "08_ty_le_vo_no_theo_muc_su_dung.csv")


def main():
    df = load()
    info = overview(df)
    overview_figure(df, info)
    structure_figure()
    target_distribution(df)
    chi = categorical(df)
    chi.to_csv(TAB / "02_chi_square.csv", index=False)
    pay_status(df)
    numeric_by_class(df)
    monthly_trends(df)
    correlation(df)
    projection(df)
    utilization(df)
    print(pd.Series(info))
    print(chi)


if __name__ == "__main__":
    main()
