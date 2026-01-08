import streamlit as st
import pandas as pd
import html
from urllib.parse import urlparse, parse_qs
st.set_page_config(
    page_title="Закупка ароматов",
    layout="wide"
)
def normalize_name(value: str) -> str:
    return (
        value.strip()              # убираем пробелы по краям
        .lower()                   # в нижний регистр
        .replace("\u00a0", " ")     # неразрывные пробелы
        .replace("  ", " ")         # двойные пробелы
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
        div[data-baseweb="input"] input {
        height: 34px;
        font-size: 0.85rem;
    }

    div[data-baseweb="select"] {
        min-height: 34px;
        font-size: 0.8rem;
    }

    div[data-baseweb="tag"] {
        font-size: 0.7rem;
        padding: 2px 6px;
    }
    .search-filter-block {
        margin-top: 6px;
        margin-bottom: 4px;
    }

    .search-filter-block .stColumn {
        padding-bottom: 0px;
    }

    .search-filter-block .stColumn > div {
    margin-bottom: 2px !important;
    }
    
    .list-container {
    padding-top: 10px;
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
    # создаём мапу: нормализованное имя → оригинальное имя столбца
    normalized_columns = {
        normalize_name(col): col
        for col in df.columns
    }

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

    if user_name in normalized_columns:
        user_column = normalized_columns[user_name]
    else:
        df[user_name] = 0
        user_column = user_name

    v1_df = pd.DataFrame({
        "aroma_name": df["Название"],
        "gender": df["пол"],
        "price_10": df["10 гр"],
        "price_50": df["50 гр"],
        "price_100": df["100 гр"],
        "ordered_ml": df[user_column].fillna(0),
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

raw_user_name = st.text_input(
    "Введите имя (как в закупочном файле):",
    value=""
)

user_name = normalize_name(raw_user_name)


view_mode = st.radio(
    "Отображение",
    ["Обзор", "Моё"],
    horizontal=True
)
search_query = ""

if user_name and "planned_ml" not in st.session_state:
    st.session_state.planned_ml = {}

if user_name:
    df_raw = load_data(SHEET_URL)
    v1_df = prepare_v1_dataframe(df_raw, user_name)

    current_sum, planned_sum = calculate_sums(v1_df)

    st.markdown(
        f"""
<div class="sticky-header">
    <div class="header-row">
        <div class="header-item">👤<br><b>{user_name}</b></div>
        <div class="header-item">💰<br><b>{current_sum:.0f} ₽</b></div>
        <div class="header-item">➕<br><b>{planned_sum:.0f} ₽</b></div>
    </div>
</div>
""",
        unsafe_allow_html=True
    )
    st.markdown('<div class="list-container">', unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .search-filter-block {
            margin-top: 6px;
            margin-bottom: 4px;
        }

        .search-filter-block div[data-testid="element-container"] {
            margin-bottom: 2px;
        }

        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown('<div class="search-filter-block">', unsafe_allow_html=True)

    search_query = st.text_input(
        "",
        placeholder="🔍 Поиск аромата"
    ).strip().lower()

    gender_filter = st.multiselect(
        "",
        options=["жен", "уни", "муж"],
        default=["жен", "уни", "муж"]
    )

    st.markdown('</div>', unsafe_allow_html=True)
    if search_query:
        v1_df = v1_df[
            v1_df["aroma_name"]
            .str.lower()
            .str.contains(search_query, na=False)
        ]

    if gender_filter:
        v1_df = v1_df[v1_df["gender"].isin(gender_filter)]

    for _, row in v1_df.iterrows():
        ordered_ml = int(row["ordered_ml"])
        row_id = row["row_id"]
        planned_ml = st.session_state.planned_ml.get(row_id, 0)

        # 🔥 РЕЖИМ "МОЁ"
        if view_mode == "Моё":
            if ordered_ml == 0 and planned_ml == 0:
                continue  # ← просто пропускаем строку

        gender = str(row["gender"])
        price = int(row["price_10"]) if row["price_10"] > 0 else None

        bg_color = "#1f3b2d" if ordered_ml > 0 else "#0e1117"

        if view_mode == "Обзор":
            right_text = f"{gender} · {price} ₽" if price is not None else gender
        else:
            right_text = f"{price} ₽ · {ordered_ml + planned_ml} мл" if price is not None else f"{ordered_ml + planned_ml} мл"
#padding:6px 10px; margin-bottom:3px межстрочный интервал
        st.markdown(
            f"""
    <div style="background-color:{bg_color}; padding:6px 10px; margin-bottom:3px; border-radius:8px; display:flex; align-items:center; gap:10px;">
        <div style="flex:1; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
            {row["aroma_name"]}
        </div>
        <div style="white-space:nowrap; font-size:0.9em; opacity:0.85;">
            {right_text}
        </div>
    </div>
    """,
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("Введите имя, чтобы загрузить данные")








