import os
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

INVENTORY_FILE = "inventory.csv"
LOG_FILE = "transactions.csv"

DEFAULT_INVENTORY = pd.DataFrame(
    [
        {"item": "종량제 봉투 20L", "category": "종량제 봉투", "qty": 120},
        {"item": "종량제 봉투 50L", "category": "종량제 봉투", "qty": 75},
        {"item": "작업용 장갑", "category": "장갑", "qty": 200},
        {"item": "강아지 사료(소형)", "category": "사료", "qty": 40},
    ]
)


def ensure_files() -> None:
    if not os.path.exists(INVENTORY_FILE):
        DEFAULT_INVENTORY.to_csv(INVENTORY_FILE, index=False, encoding="utf-8-sig")
    if not os.path.exists(LOG_FILE):
        pd.DataFrame(columns=["datetime", "item", "category", "type", "amount"]).to_csv(
            LOG_FILE, index=False, encoding="utf-8-sig"
        )


@st.cache_data(ttl=60)
def load_inventory() -> pd.DataFrame:
    return pd.read_csv(INVENTORY_FILE, encoding="utf-8-sig")


@st.cache_data(ttl=60)
def load_logs() -> pd.DataFrame:
    return pd.read_csv(LOG_FILE, encoding="utf-8-sig")


def save_inventory(df: pd.DataFrame) -> None:
    df.to_csv(INVENTORY_FILE, index=False, encoding="utf-8-sig")


def append_log(item: str, category: str, tx_type: str, amount: int) -> None:
    row = pd.DataFrame(
        [
            {
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "item": item,
                "category": category,
                "type": tx_type,
                "amount": amount,
            }
        ]
    )
    row.to_csv(
        LOG_FILE,
        mode="a",
        index=False,
        header=not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0,
        encoding="utf-8-sig",
    )


def preprocess_logs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["datetime", "item", "category", "type", "amount", "signed_amount"])

    cleaned = df.dropna(subset=["datetime", "item", "type", "amount"]).copy()
    cleaned["datetime"] = pd.to_datetime(cleaned["datetime"], errors="coerce")
    cleaned = cleaned.dropna(subset=["datetime"])
    cleaned["amount"] = pd.to_numeric(cleaned["amount"], errors="coerce").fillna(0).astype(int)
    cleaned["signed_amount"] = cleaned.apply(
        lambda x: x["amount"] if x["type"] == "입고(+)" else -x["amount"], axis=1
    )
    return cleaned


def build_report_tables(
    inventory_df: pd.DataFrame, logs_df: pd.DataFrame, year: int, month: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    month_start = pd.Timestamp(year=year, month=month, day=1)
    month_end = month_start + pd.offsets.MonthBegin(1)

    monthly_logs = logs_df[
        (logs_df["datetime"] >= month_start) & (logs_df["datetime"] < month_end)
    ].copy()
    logs_after_month_start = logs_df[logs_df["datetime"] >= month_start].copy()

    month_in = (
        monthly_logs[monthly_logs["type"] == "입고(+)"].groupby("item")["amount"].sum()
        if not monthly_logs.empty
        else pd.Series(dtype="int64")
    )
    month_out = (
        monthly_logs[monthly_logs["type"] == "출고(-)"].groupby("item")["amount"].sum()
        if not monthly_logs.empty
        else pd.Series(dtype="int64")
    )
    net_after_start = (
        logs_after_month_start.groupby("item")["signed_amount"].sum()
        if not logs_after_month_start.empty
        else pd.Series(dtype="int64")
    )

    summary_df = inventory_df.copy()
    summary_df["현재고"] = summary_df["qty"].astype(int)
    summary_df["전월 이월량"] = (
        summary_df["현재고"] - summary_df["item"].map(net_after_start).fillna(0).astype(int)
    ).astype(int)
    summary_df["당월 입고 합계"] = summary_df["item"].map(month_in).fillna(0).astype(int)
    summary_df["당월 출고 합계"] = summary_df["item"].map(month_out).fillna(0).astype(int)
    summary_df = summary_df[
        ["category", "item", "전월 이월량", "당월 입고 합계", "당월 출고 합계", "현재고"]
    ].rename(columns={"category": "카테고리", "item": "품목"})

    detail_df = monthly_logs.sort_values("datetime", ascending=True).copy()
    if not detail_df.empty:
        detail_df["일시"] = detail_df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
        detail_df = detail_df[["일시", "item", "category", "type", "amount"]]
        detail_df.columns = ["일시", "품목", "카테고리", "구분", "수량"]
    else:
        detail_df = pd.DataFrame(columns=["일시", "품목", "카테고리", "구분", "수량"])

    return summary_df, detail_df


def to_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    output.seek(0)
    return output.getvalue()


def apply_mobile_styles(enabled: bool) -> None:
    if not enabled:
        return

    st.markdown(
        """
        <style>
        @media (max-width: 768px) {
            .block-container {
                padding-top: 0.8rem !important;
                padding-left: 0.8rem !important;
                padding-right: 0.8rem !important;
            }
            h1 { font-size: 1.5rem !important; }
            h2 { font-size: 1.25rem !important; }
            h3 { font-size: 1.1rem !important; }
            p, label { font-size: 0.95rem !important; }
            .stButton button, .stDownloadButton button {
                width: 100% !important;
                min-height: 2.6rem !important;
            }
            [data-testid="stMetric"] {
                padding: 0.45rem !important;
            }
            [data-testid="stMetricLabel"] {
                font-size: 0.85rem !important;
            }
            [data-testid="stMetricValue"] {
                font-size: 1.2rem !important;
            }
            .mobile-scroll {
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }
            .mobile-scroll table {
                min-width: 680px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="소모품 재고 관리", page_icon="📦", layout="wide")

ensure_files()
inventory = load_inventory()
logs = preprocess_logs(load_logs())

menu = st.sidebar.radio("메뉴", ["현재 재고 관리", "월간 보고서"])
mobile_mode = st.sidebar.checkbox("모바일 최적화 보기", value=False)
apply_mobile_styles(mobile_mode)

if menu == "현재 재고 관리":
    st.title("📦 소모품 재고 관리 시스템")
    categories = ["전체"] + sorted(inventory["category"].unique().tolist())
    selected_category = st.sidebar.selectbox("소모품 종류 선택", categories)

    if selected_category == "전체":
        filtered_inventory = inventory.copy()
    else:
        filtered_inventory = inventory[inventory["category"] == selected_category].copy()

    st.subheader("현재 재고 수량")
    if filtered_inventory.empty:
        st.info("선택한 카테고리에 해당하는 품목이 없습니다.")
    else:
        metric_col_count = 1 if mobile_mode else min(4, len(filtered_inventory))
        metric_cols = st.columns(metric_col_count)
        for idx, (_, row) in enumerate(filtered_inventory.iterrows()):
            with metric_cols[idx % len(metric_cols)]:
                st.metric(row["item"], f"{int(row['qty'])} 개")
                if int(row["qty"]) < 20:
                    st.error("⚠️ 재고 부족: 즉시 구매 필요")

    st.divider()
    if mobile_mode:
        left = st.container()
        right = st.container()
    else:
        left, right = st.columns([1, 1.3], gap="large")

    with left:
        st.subheader("입/출고 입력")
        with st.form("update_form"):
            item = st.selectbox("품목 선택", inventory["item"].tolist())
            tx_type = st.radio("구분", ["입고(+)", "출고(-)"], horizontal=True)
            amount = st.number_input("수량", min_value=1, step=1, value=1)
            submit = st.form_submit_button("기록하기")

            if submit:
                target_idx = inventory.index[inventory["item"] == item][0]
                current_qty = int(inventory.loc[target_idx, "qty"])

                if tx_type == "출고(-)" and amount > current_qty:
                    st.error(f"재고 부족: 현재 {current_qty}개만 출고할 수 있습니다.")
                else:
                    delta = amount if tx_type == "입고(+)" else -amount
                    inventory.loc[target_idx, "qty"] = current_qty + delta
                    save_inventory(inventory)
                    append_log(
                        item=item,
                        category=inventory.loc[target_idx, "category"],
                        tx_type=tx_type,
                        amount=int(amount),
                    )
                    load_inventory.clear()
                    load_logs.clear()
                    inventory = load_inventory()
                    logs = preprocess_logs(load_logs())
                    st.success(f"{item} {int(amount)}개 {tx_type} 완료!")
                    # st.rerun()

    with right:
        st.subheader("최근 기록")
        if logs.empty:
            st.caption("아직 기록이 없습니다.")
        else:
            recent_logs = logs.sort_values("datetime", ascending=False).head(15).copy()
            recent_logs["datetime"] = recent_logs["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
            recent_logs = recent_logs[["datetime", "item", "category", "type", "amount"]]
            recent_logs.columns = ["일시", "품목", "카테고리", "구분", "수량"]
            st.dataframe(recent_logs, use_container_width=True, hide_index=True)

else:
    current_year = datetime.now().year
    years = list(range(current_year - 5, current_year + 2))
    selected_year = st.sidebar.selectbox("연도 선택", years, index=years.index(current_year))
    selected_month = st.sidebar.selectbox("월 선택", list(range(1, 13)), index=datetime.now().month - 1)
    print_mode = st.sidebar.checkbox("인쇄용 보기", value=True)

    if print_mode:
        st.markdown(
            """
            <style>
            @media print {
                section[data-testid="stSidebar"] { display: none !important; }
                button, .stDownloadButton { display: none !important; }
                .block-container { padding-top: 0.6rem !important; }
            }
            .print-title {
                text-align: center;
                font-size: 2.0rem;
                font-weight: 700;
                margin-bottom: 0.4rem;
            }
            .print-meta {
                text-align: right;
                font-size: 0.95rem;
                margin-bottom: 1rem;
            }
            .print-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.95rem;
                margin-bottom: 1rem;
            }
            .print-table th, .print-table td {
                border: 1px solid #333;
                padding: 6px 8px;
                text-align: center;
            }
            .print-table th {
                background-color: #f4f4f4;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div class='print-title'>대전반려동물공원 소모품 월간 보고서 ({selected_year}년 {selected_month}월)</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='print-meta'>작성일: {datetime.now().strftime('%Y-%m-%d')}</div>",
        unsafe_allow_html=True,
    )

    summary_df, detail_df = build_report_tables(inventory, logs, selected_year, selected_month)
    sorted_summary = summary_df.sort_values(["카테고리", "품목"]).reset_index(drop=True)

    st.markdown("### 품목별 요약")
    if print_mode:
        st.markdown(
            f"<div class='mobile-scroll'>{sorted_summary.to_html(index=False, classes='print-table', border=0)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.dataframe(sorted_summary, use_container_width=True, hide_index=True)

    st.markdown("### 입출고 상세 내역")
    if detail_df.empty:
        st.caption("선택한 달의 입출고 내역이 없습니다.")
    elif print_mode:
        st.markdown(
            f"<div class='mobile-scroll'>{detail_df.to_html(index=False, classes='print-table', border=0)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

    excel_bytes = to_excel_bytes(detail_df, "월간 입출고 내역")
    st.download_button(
        label="입출고 내역 엑셀 다운로드 (.xlsx)",
        data=excel_bytes,
        file_name=f"transactions_{selected_year}_{selected_month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
