import streamlit as st
import pandas as pd
from urllib.parse import urlparse, parse_qs
st.set_page_config(
    page_title="Закупка ароматов",
    layout="wide"
)

st.markdown(
    """
    <style>
    .sticky-header {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: #0e1117;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid #333;
    }
    .header-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        font-size: 0.9rem;
    }
    .header-item {
        flex: 1;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1lBJoT4Wws6FHAt91G3ojeTycdYILBDw76M8o_9bept8/edit?gid=0#gid=0"


def make_csv_url(sheet_url: str) -> str:
    """
    Превращает обычную ссылку Google Sheets в CSV-ссылку
    """
    parsed = urlparse(sheet_url)

    # получаем ID таблицы
    path_parts = parsed.path.split("/")
    spreadsheet_id = path_parts[path_parts.index("d") + 1]

    # получаем gid (если есть)
    query = parse_qs(parsed.query)
    gid = query.get("gid", ["0"])[0]

    return (
        f"https://docs.google.com/spreadsheets/d/"
        f"{spreadsheet_id}/export?format=csv&gid={gid}"
    )


def load_data(sheet_url: str) -> pd.DataFrame:
    csv_url = make_csv_url(sheet_url)
    df = pd.read_csv(csv_url, engine="python")
    return df



def calculate_sums(df: pd.DataFrame) -> tuple[float, float]:
    current_sum = (df["ordered_ml"] / 10 * df["price_10"]).sum()

    planned_sum = 0
    for _, row in df.iterrows():
        row_id = row["row_id"]
        planned_ml = st.session_state.planned_ml.get(row_id, 0)
        planned_sum += (planned_ml / 10) * row["price_10"]

    return current_sum, planned_sum

def add_planned_ml(row_id: int):
    st.session_state.planned_ml[row_id] = (
        st.session_state.planned_ml.get(row_id, 0) + 10
    )


def prepare_v1_dataframe(
    df: pd.DataFrame,
    user_name: str
) -> pd.DataFrame:
    """
    Приводит сырые данные из Google Sheets к формату v1
    """

    required_columns = [
        "Название",
        "пол",
        "10 гр",
        "50 гр",
        "100 гр",
    ]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Отсутствует обязательный столбец: {col}")

    if user_name not in df.columns:
        df[user_name] = 0

    v1_df = pd.DataFrame({
        "aroma_name": df["Название"],
        "gender": df["пол"],
        "price_10": df["10 гр"],
        "price_50": df["50 гр"],
        "price_100": df["100 гр"],
        "ordered_ml": df[user_name].fillna(0),
    })
    # --- важно: сбрасываем индекс ---
    v1_df = v1_df.reset_index(drop=True)
    v1_df["price_10"] = (
        v1_df["price_10"]
        .astype(str)
        .str.replace(r"[^\d.,]", "", regex=True)  # убираем ₽, пробелы, всё лишнее
        .str.replace(",", ".", regex=False)
    )

    v1_df["price_10"] = pd.to_numeric(v1_df["price_10"], errors="coerce").fillna(0)

    # --- служебный идентификатор строки ---
    v1_df["row_id"] = v1_df.index
    # --- пользовательские поля ---

    v1_df["link"] = ""

    return v1_df


st.title("🧴 Закупка ароматов")

user_name = st.text_input(
    "Введите имя (как в закупочном файле):",
    value=""
)

if user_name and "planned_ml" not in st.session_state:
    st.session_state.planned_ml = {}

if user_name:
    # 1. загружаем сырые данные
    df_raw = load_data(SHEET_URL)
    # 2. готовим v1 DataFrame
    v1_df = prepare_v1_dataframe(df_raw, user_name)
   # считаем суммы
    current_sum, planned_sum = calculate_sums(v1_df)

    # 5. рисуем шапку
    st.markdown(
        f"""
        <div class="sticky-header">
            <div class="header-row">
                <div class="header-item">
                    👤<br><b>{user_name}</b>
                </div>
                <div class="header-item">
                    💰<br><b>{current_sum:.0f} ₽</b>
                </div>
                <div class="header-item">
                    ➕<br><b>{planned_sum:.0f} ₽</b>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 6. ТОЛЬКО отрисовка строк + кнопки
    for _, row in v1_df.iterrows():
        row_id = row["row_id"]

        col_btn, col_name, col_gender, col_price, col_ordered, col_planned = st.columns(
            [1, 4, 2, 2, 2, 2]
        )

        with col_btn:
            st.button(
                "➕",
                key=f"plus_{row_id}",
                on_click=add_planned_ml,
                args=(row_id,)
            )

        with col_name:
            st.write(row["aroma_name"])

        with col_gender:
            st.write(row["gender"])
        with col_price:
            price = int(row["price_10"])
            st.write(f"{price} ₽ / 10 мл" if price > 0 else "—")

        with col_ordered:
            st.write(f"{int(row['ordered_ml'])} мл")

        with col_planned:
            planned_ml = st.session_state.planned_ml.get(row_id, 0)
            st.write(f"{planned_ml} мл")



else:
    st.info("Введите имя, чтобы загрузить данные")




