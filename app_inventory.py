"""
종량제 봉투 재고 관리 — Streamlit
실행: streamlit run app_inventory.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent
INVENTORY_FILE = BASE / "inventory.csv"
LOG_FILE = BASE / "transactions.csv"


def ensure_files() -> None:
    if not INVENTORY_FILE.exists():
        df = pd.DataFrame(
            [
                {"품목": "종량제 10L", "카테고리": "일반용", "현재고": 100},
                {"품목": "종량제 20L", "카테고리": "일반용", "현재고": 150},
                {"품목": "종량제 50L", "카테고리": "일반용", "현재고": 50},
                {"품목": "불연성마대 50L", "카테고리": "특수용", "현재고": 30},
            ]
        )
        df.to_csv(INVENTORY_FILE, index=False, encoding="utf-8-sig")

    if not LOG_FILE.exists():
        df_log = pd.DataFrame(columns=["일시", "품목", "구분", "수량", "담당자"])
        df_log.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")


def load_data(file: Path) -> pd.DataFrame:
    return pd.read_csv(file, encoding="utf-8-sig")


def save_data(df: pd.DataFrame, file: Path) -> None:
    df.to_csv(file, index=False, encoding="utf-8-sig")


st.set_page_config(page_title="종량제 봉투 재고관리", layout="wide")
ensure_files()

menu = st.sidebar.radio("메뉴 선택", ["재고 현황 및 입출고", "입출고 이력 확인"])

if menu == "재고 현황 및 입출고":
    st.title("📦 종량제 봉투 재고 관리")

    inventory = load_data(INVENTORY_FILE)

    cols = st.columns(len(inventory))
    for idx, row in inventory.iterrows():
        with cols[idx]:
            st.metric(label=row["품목"], value=f"{row['현재고']} 개")
            if row["현재고"] < 20:
                st.error("⚠️ 재고 부족")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📥 입출고 기록")
        with st.form("inventory_form", clear_on_submit=True):
            item = st.selectbox("품목 선택", inventory["품목"].tolist())
            move_type = st.radio("구분", ["입고", "출고"], horizontal=True)
            amount = st.number_input("수량", min_value=1, step=1)
            manager = st.text_input("담당자 성함")
            submit = st.form_submit_button("기록하기")

            if submit:
                row_idx = inventory.index[inventory["품목"] == item][0]
                current_qty = inventory.at[row_idx, "현재고"]

                if move_type == "출고" and current_qty < amount:
                    st.error("재고가 부족하여 출고할 수 없습니다.")
                else:
                    new_qty = (
                        current_qty + amount
                        if move_type == "입고"
                        else current_qty - amount
                    )
                    inventory.at[row_idx, "현재고"] = new_qty
                    save_data(inventory, INVENTORY_FILE)

                    new_log = pd.DataFrame(
                        [
                            {
                                "일시": datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "품목": item,
                                "구분": move_type,
                                "수량": amount,
                                "담당자": manager,
                            }
                        ]
                    )
                    log_df = load_data(LOG_FILE)
                    pd.concat([log_df, new_log], ignore_index=True).to_csv(
                        LOG_FILE, index=False, encoding="utf-8-sig"
                    )

                    st.success(f"{item} {amount}개 {move_type} 처리되었습니다.")
                    st.rerun()

    with col2:
        st.subheader("📊 현재고 상세표")
        st.dataframe(inventory, use_container_width=True, hide_index=True)

elif menu == "입출고 이력 확인":
    st.title("📜 전체 입출고 이력")
    logs = load_data(LOG_FILE)
    if not logs.empty:
        st.dataframe(
            logs.sort_values(by="일시", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

        csv = logs.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            "이력 다운로드 (CSV)",
            csv,
            "inventory_logs.csv",
            "text/csv",
        )
    else:
        st.info("아직 기록된 이력이 없습니다.")
