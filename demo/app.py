"""Demo tương tác: streamlit run demo/app.py (chạy từ thư mục gốc dự án)."""
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.evaluation import load_split  # noqa: E402
from src.preprocessing import (BILL, DATA, FEATURES, PAY, PAYMENT, TARGET, add_features,  # noqa: E402
                               clean_data, make_preprocessor)

SEED = 42
MONTHS = ["Tháng 9", "Tháng 8", "Tháng 7", "Tháng 6", "Tháng 5", "Tháng 4"]
SEX = {1: "Nam", 2: "Nữ"}
EDU = {1: "Sau đại học", 2: "Đại học", 3: "THPT", 4: "Khác"}
MAR = {1: "Đã kết hôn", 2: "Độc thân", 3: "Khác"}
PAY_LABEL = {-2: "−2 (mã chưa được mô tả)", -1: "−1 · trả đúng hạn", 0: "0 (mã chưa được mô tả)",
             **{k: f"{k} · trễ {k} tháng" for k in range(1, 9)}, 9: "9 · trễ từ 9 tháng"}
MODELS = {"HistGradientBoosting (mô hình đề xuất)": "hgb", "Logistic Regression (mô hình cơ sở)": "lr"}

st.set_page_config(page_title="Demo dự đoán vỡ nợ – Nhóm 13", page_icon="💳", layout="wide")


# ---------- dữ liệu và mô hình (tính một lần, lưu cache) ----------
@st.cache_data(show_spinner="Đang đọc dữ liệu…")
def load_data():
    df, _, _, _ = clean_data(pd.read_excel(DATA, header=1))
    parts = load_split(df)
    return df, parts["train"], parts["validation"], parts["test"]


@st.cache_resource(show_spinner="Đang huấn luyện hai mô hình theo cấu hình nhóm đã chọn…")
def train_models():
    _, train, _, _ = load_data()
    hgb = Pipeline([("pre", make_preprocessor("tree", with_features=True)),
                    ("clf", HistGradientBoostingClassifier(max_iter=150, learning_rate=0.1, early_stopping=False,
                                                           l2_regularization=10.0, max_leaf_nodes=7,
                                                           random_state=SEED))])
    lr = Pipeline([("pre", make_preprocessor("linear", with_features=False)),
                   ("clf", LogisticRegression(C=10.0, max_iter=3000, random_state=SEED))])
    X, y = train[FEATURES], train[TARGET]
    return {"hgb": hgb.fit(X, y), "lr": lr.fit(X, y)}


@st.cache_data
def scores(model_key, split):
    _, _, val, test = load_data()
    part = val if split == "validation" else test
    return train_models()[model_key].predict_proba(part[FEATURES])[:, 1], part[TARGET].to_numpy()


def best_threshold(p, y, cost_fn, cost_fp=1.0):
    """Ngưỡng cho chi phí (cost_fn·FN + cost_fp·FP) nhỏ nhất – giống cách chọn trên validation trong báo cáo."""
    cand = np.append(np.unique(p), np.inf)
    order = np.argsort(p)
    ps, ys = p[order], y[order]
    below = np.searchsorted(ps, cand, side="left")             # số khách có điểm < ngưỡng (không cảnh báo)
    fn = np.concatenate([[0], np.cumsum(ys == 1)])[below]      # vỡ nợ nhưng không bị cảnh báo
    fp = (ys == 0).sum() - np.concatenate([[0], np.cumsum(ys == 0)])[below]  # tốt nhưng bị cảnh báo
    cost = cost_fn * fn + cost_fp * fp
    return float(cand[np.argmin(cost)])


def confusion(p, y, t):
    pred = p >= t
    return dict(TP=int((pred & (y == 1)).sum()), FN=int((~pred & (y == 1)).sum()),
                FP=int((pred & (y == 0)).sum()), TN=int((~pred & (y == 0)).sum()))


def fmt(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


def money(x):
    return f"{x:,.0f}".replace(",", ".")


# ---------- giao diện ----------
st.title("💳 Dự đoán khả năng vỡ nợ thẻ tín dụng")
st.caption("Demo của Nhóm 13 – học phần Nhận dạng mẫu. Dữ liệu: UCI Default of Credit Card Clients (Đài Loan, 2005). "
           "Mô hình được huấn luyện trên tập train theo đúng cấu hình trong báo cáo.")

df, train, val, test = load_data()
models = train_models()

with st.sidebar:
    st.header("Thiết lập")
    model_name = st.radio("Mô hình", list(MODELS))
    model_key = MODELS[model_name]
    ratio = st.slider("Bỏ sót 1 người vỡ nợ tốn gấp mấy lần nhắc nhầm 1 người tốt?", 1, 10, 5)
    p_val, y_val = scores(model_key, "validation")
    threshold = best_threshold(p_val, y_val, ratio)
    st.metric("Ngưỡng cảnh báo (chọn trên validation)", fmt(threshold))
    st.caption(f"Ngưỡng lý thuyết theo quy tắc Bayes: 1/(1+{ratio}) = {fmt(1 / (1 + ratio))}")
    st.divider()
    st.caption(f"Train {len(train):,} · Validation {len(val):,} · Test {len(test):,} khách hàng".replace(",", "."))

tab1, tab2, tab3 = st.tabs(["👤 Dự đoán cho một khách hàng", "⚖️ Chọn ngưỡng theo chi phí", "🔍 Khám phá dữ liệu"])

# ===== Tab 1: một khách hàng =====
with tab1:
    if "cust" not in st.session_state:
        st.session_state.cust = test.iloc[0]
    c1, c2, c3 = st.columns(3)
    if c1.button("🎲 Lấy ngẫu nhiên một khách hàng trong tập test", width="stretch"):
        st.session_state.cust = test.sample(1).iloc[0]
    if c2.button("⚠️ Ví dụ: khách hay trễ hạn", width="stretch"):
        st.session_state.cust = test[(test.PAY_0 >= 2) & (test.PAY_2 >= 2)].iloc[0]
    if c3.button("✅ Ví dụ: khách trả đúng hạn", width="stretch"):
        st.session_state.cust = test[(test[PAY] == -1).all(axis=1)].iloc[0]
    cust = st.session_state.cust

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("Thông tin khách hàng")
        k = int(cust.ID)  # khóa theo khách hàng: đổi khách thì mọi ô nhập được nạp lại
        a, b, c = st.columns(3)
        limit = a.number_input("Hạn mức (NT$)", 10_000, 1_000_000, int(cust.LIMIT_BAL), step=10_000, key=f"lim{k}")
        age = b.number_input("Tuổi", 21, 79, int(cust.AGE), key=f"age{k}")
        sex = c.selectbox("Giới tính", list(SEX), index=list(SEX).index(int(cust.SEX)), format_func=SEX.get,
                          key=f"sex{k}")
        a, b = st.columns(2)
        edu = a.selectbox("Học vấn", list(EDU), index=list(EDU).index(int(cust.EDUCATION)), format_func=EDU.get,
                          key=f"edu{k}")
        mar = b.selectbox("Hôn nhân", list(MAR), index=list(MAR).index(int(cust.MARRIAGE)), format_func=MAR.get,
                          key=f"mar{k}")

        st.markdown("**Trạng thái trả nợ 6 tháng** (tháng 9 là gần nhất)")
        cols = st.columns(6)
        pays = [cols[i].selectbox(MONTHS[i], list(PAY_LABEL), index=list(PAY_LABEL).index(int(cust[PAY[i]])),
                                  format_func=PAY_LABEL.get, key=f"pay{i}_{k}") for i in range(6)]

        st.markdown("**Dư nợ và số tiền đã trả (NT$)** – sửa trực tiếp trong bảng")
        money_df = pd.DataFrame([[int(cust[c]) for c in BILL], [int(cust[c]) for c in PAYMENT]],
                                index=["Dư nợ sao kê", "Đã thanh toán"], columns=MONTHS)
        edited = st.data_editor(money_df, width="stretch", key=f"money{cust.ID}")

    row = {"LIMIT_BAL": limit, "SEX": sex, "EDUCATION": edu, "MARRIAGE": mar, "AGE": age,
           **dict(zip(PAY, pays)), **dict(zip(BILL, edited.loc["Dư nợ sao kê"].astype(float))),
           **dict(zip(PAYMENT, edited.loc["Đã thanh toán"].astype(float)))}
    X_one = pd.DataFrame([row])[FEATURES]
    if (X_one[PAYMENT] < 0).any(axis=None):
        st.error("Số tiền đã thanh toán không được âm.")
        st.stop()
    prob = float(models[model_key].predict_proba(X_one)[0, 1])
    other_key = "lr" if model_key == "hgb" else "hgb"
    prob_other = float(models[other_key].predict_proba(X_one)[0, 1])
    other_thr = best_threshold(*scores(other_key, "validation"), ratio)

    with right:
        st.subheader("Kết quả")
        warn = prob >= threshold
        st.metric("Xác suất vỡ nợ tháng tới", f"{fmt(prob * 100, 1)}%")
        st.progress(min(prob, 1.0))
        if warn:
            st.error(f"⚠️ **Cảnh báo** – xác suất ≥ ngưỡng {fmt(threshold)}")
        else:
            st.success(f"✅ **Không cảnh báo** – xác suất < ngưỡng {fmt(threshold)}")
        other_name = [k for k, v in MODELS.items() if v == other_key][0].split(" (")[0]
        st.caption(f"{other_name}: {fmt(prob_other * 100, 1)}% → "
                   f"{'cảnh báo' if prob_other >= other_thr else 'không cảnh báo'} (ngưỡng {fmt(other_thr)})")

        unchanged = (X_one.iloc[0].astype(float).values == cust[FEATURES].astype(float).values).all()
        if unchanged:
            truth = "**đã vỡ nợ**" if cust[TARGET] == 1 else "**không vỡ nợ**"
            st.info(f"Khách hàng ID {int(cust.ID)} trong tập test thực tế {truth} ở tháng 10/2005.")
        else:
            st.info("Bạn đã chỉnh thông tin, nên đây là một khách hàng giả định.")

        st.markdown("**Các đặc trưng hành vi mô hình tính thêm**")
        f = add_features(X_one).iloc[0]
        st.dataframe(pd.DataFrame({
            "Đặc trưng": ["Số tháng trễ hạn", "Mức trễ nặng nhất", "Thay đổi trễ hạn tháng gần nhất",
                          "Mức dùng hạn mức tháng 9", "Thanh toán trung bình (NT$)", "Số tháng không trả"],
            "Giá trị": [f"{int(f.late_month_count)}", f"{int(f.max_delay)}", f"{int(f.recent_delay_change):+d}",
                        f"{fmt(f.utilization_sep * 100, 0)}%", money(f.mean_payment), f"{int(f.zero_payment_count)}"]}),
            hide_index=True, width="stretch")

# ===== Tab 2: ngưỡng và chi phí =====
with tab2:
    st.markdown(f"Bỏ sót một người vỡ nợ bị phạt **{ratio} điểm**, nhắc nhầm một người tốt bị phạt **1 điểm**. "
                "Ngưỡng được chọn trên **validation** sao cho tổng điểm phạt nhỏ nhất, rồi giữ nguyên để chấm trên **test**. "
                "Kéo thanh bên trái để đổi tỷ lệ phạt, hoặc tự chỉnh ngưỡng bên dưới.")
    manual = st.slider("Ngưỡng đang dùng", 0.0, 1.0, float(min(threshold, 1.0)), 0.005, format="%.3f")
    p_test, y_test = scores(model_key, "test")
    cm = confusion(p_test, y_test, manual)
    n = len(y_test)
    cost = (ratio * cm["FN"] + cm["FP"]) / n
    recall = cm["TP"] / (cm["TP"] + cm["FN"])
    precision = cm["TP"] / max(cm["TP"] + cm["FP"], 1)

    m = st.columns(5)
    m[0].metric("Phát hiện đúng (TP)", money(cm["TP"]))
    m[1].metric("Bỏ sót (FN)", money(cm["FN"]))
    m[2].metric("Nhắc nhầm (FP)", money(cm["FP"]))
    m[3].metric("Recall", fmt(recall))
    m[4].metric("Chi phí trung bình / khách", fmt(cost))
    st.caption(f"Tập test: {money(n)} khách hàng, {money(y_test.sum())} vỡ nợ. Precision {fmt(precision)} · "
               f"Accuracy {fmt((cm['TP'] + cm['TN']) / n)} · Nếu không cảnh báo ai, chi phí là {fmt(ratio * y_test.sum() / n)}")

    grid = np.linspace(0.01, 0.9, 90)
    curve = pd.DataFrame({"Ngưỡng": grid,
                          "Chi phí trên validation": [(ratio * confusion(p_val, y_val, t)["FN"] +
                                                       confusion(p_val, y_val, t)["FP"]) / len(y_val) for t in grid]})
    line = alt.Chart(curve).mark_line(color="#2F6496", strokeWidth=3).encode(
        x=alt.X("Ngưỡng:Q", title="Ngưỡng cảnh báo"), y=alt.Y("Chi phí trên validation:Q", title="Chi phí trung bình / khách"))
    rules = alt.Chart(pd.DataFrame({"x": [threshold, manual], "Loại": ["Ngưỡng tối ưu", "Ngưỡng đang dùng"]})).mark_rule(
        strokeWidth=2, strokeDash=[6, 4]).encode(x="x:Q", color=alt.Color("Loại:N", scale=alt.Scale(
            domain=["Ngưỡng tối ưu", "Ngưỡng đang dùng"], range=["#C2621F", "#7A8698"]), title=None))
    st.altair_chart((line + rules).properties(height=340), width="stretch")
    st.caption("Đường cong tính trên validation; chi phí thấp nhất ở ngưỡng tối ưu. Ngưỡng mặc định 0,5 thường cho chi phí cao hơn "
               "vì bỏ sót nhiều người vỡ nợ.")

# ===== Tab 3: khám phá dữ liệu =====
with tab3:
    st.markdown("Lọc khách hàng trong toàn bộ 29.965 hồ sơ đã làm sạch và xem tỷ lệ vỡ nợ thay đổi thế nào.")
    data = add_features(df[FEATURES]).assign(default=df[TARGET].values)
    a, b, c = st.columns(3)
    lim = a.slider("Hạn mức (NT$)", 10_000, 1_000_000, (10_000, 1_000_000), step=10_000)
    ages = b.slider("Tuổi", 21, 79, (21, 79))
    sexes = c.multiselect("Giới tính", list(SEX), default=list(SEX), format_func=SEX.get)
    sel = data[data.LIMIT_BAL.between(*lim) & data.AGE.between(*ages) & data.SEX.isin(sexes)]

    m = st.columns(3)
    m[0].metric("Số khách hàng", money(len(sel)))
    m[1].metric("Tỷ lệ vỡ nợ", f"{fmt(sel.default.mean() * 100 if len(sel) else 0, 1)}%")
    m[2].metric("So với toàn bộ dữ liệu", f"{fmt(data.default.mean() * 100, 1)}%")

    group = st.selectbox("Xem tỷ lệ vỡ nợ theo", ["Số tháng trễ hạn trong 6 tháng", "Trạng thái trả nợ tháng 9",
                                                  "Nhóm tuổi", "Nhóm hạn mức", "Học vấn"])
    if group == "Số tháng trễ hạn trong 6 tháng":
        key = sel.late_month_count.astype(str)
    elif group == "Trạng thái trả nợ tháng 9":
        key = sel.PAY_0.clip(upper=4).map(lambda v: "≥ 4" if v == 4 else str(v))
    elif group == "Nhóm tuổi":
        key = pd.cut(sel.AGE, [20, 24, 29, 34, 39, 49, 59, 80],
                     labels=["21–24", "25–29", "30–34", "35–39", "40–49", "50–59", "≥ 60"]).astype(str)
    elif group == "Nhóm hạn mức":
        key = pd.cut(sel.LIMIT_BAL, [0, 50_000, 100_000, 180_000, 270_000, 1_000_000],
                     labels=["≤ 50k", "50–100k", "100–180k", "180–270k", "> 270k"]).astype(str)
    else:
        key = sel.EDUCATION.map(EDU)
    agg = sel.groupby(key, observed=True).default.agg(["mean", "size"]).reset_index()
    agg.columns = ["Nhóm", "Tỷ lệ vỡ nợ", "Số khách"]
    agg = agg[agg["Số khách"] >= 20]
    bars = alt.Chart(agg).mark_bar(color="#2F6496", cornerRadiusEnd=4).encode(
        x=alt.X("Nhóm:N", sort=None, title=group),
        y=alt.Y("Tỷ lệ vỡ nợ:Q", axis=alt.Axis(format="%"), title="Tỷ lệ vỡ nợ"),
        tooltip=["Nhóm", alt.Tooltip("Tỷ lệ vỡ nợ:Q", format=".1%"), "Số khách"])
    avg = alt.Chart(pd.DataFrame({"y": [data.default.mean()]})).mark_rule(color="#C2621F", strokeDash=[6, 4],
                                                                           strokeWidth=2).encode(y="y:Q")
    st.altair_chart((bars + avg).properties(height=360), width="stretch")
    st.caption("Đường nét đứt màu cam: tỷ lệ vỡ nợ chung 22,1%. Chỉ hiện các nhóm có từ 20 khách hàng.")
