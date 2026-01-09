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
# ===============================
# НАСТРОЙКИ РАЗРАБОТЧИКА
# Менять ТОЛЬКО здесь
# ===============================

# Google Sheets
SHEET_URL = "https://docs.google.com/spreadsheets/d/12VphWS6CAQE4vMLNY9wOdSooIopiSbuKjIZv07zJzL0/edit?gid=0#gid=0"

# Тексты для сообщений в Telegram
ORDER_TAGS = "#Luziянварь"
REORDER_TAGS = "#Luziянварь #добор"

# НАСТРОЙКИ СВЕТОМУЗЫКИ
# ===============================

ENABLE_LIGHTSHOW = False    # True включать ТОЛЬКО в последний день, False выключить

TOTAL_REQUIRED_ML = 100    # при этом количестве тревоги нет
WARNING_THRESHOLD = 70      # начинаем волноваться
CRITICAL_THRESHOLD = 30     # паника
# ЧТОБЫ У МЕНЯ НЕ УМЕР ПАЛЕЦ
# ===============================
SECTION_ANCHOR_KEYWORD = "Al Rehab Choco Musk"


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

def extract_first_valid_number(row: pd.Series) -> float | None:
    for value in row:
        try:
            num = float(str(value).replace(",", "."))
            if num > 0:
                return num
        except (ValueError, TypeError):
            continue
    return None


def calculate_sums(df: pd.DataFrame) -> tuple[float, float]:
    current_sum = (df["ordered_ml"] / 10 * df["price"]).sum()

    planned_sum = 0
    for _, row in df.iterrows():
        row_id = row["row_id"]
        planned_ml = st.session_state.planned_ml.get(row_id, 0)
        planned_sum += (planned_ml / 10) * row["price"]

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

    # --- ищем колонку с названием аромата гибко ---
    name_column = None

    for col in df.columns:
        if "название" in col.lower():
            name_column = col
            break

    if name_column is None:
        raise ValueError("Не удалось найти столбец с названием аромата")

    if user_name in normalized_columns:
        user_column = normalized_columns[user_name]
    else:
        df[user_name] = 0
        user_column = user_name

    v1_df = pd.DataFrame({
        "aroma_name": df[name_column],
        "ordered_ml": df[user_column].fillna(0),
        "total_collected": df["Набрано"].fillna(0) if "Набрано" in df.columns else 0,
    })
    # вычисляем цену как первое валидное число в строке
    v1_df["price"] = df.apply(extract_first_valid_number, axis=1).fillna(0)

    # --- важно: сбрасываем индекс ---
    v1_df = v1_df.reset_index(drop=True)
    v1_df["price"] = (
        v1_df["price"]
        .astype(str)
        .str.replace(r"[^\d.,]", "", regex=True)  # убираем ₽, пробелы, всё лишнее
        .str.replace(",", ".", regex=False)
    )

    v1_df["price"] = pd.to_numeric(v1_df["price"], errors="coerce").fillna(0)

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

mode_col, anchor_col = st.columns([3, 2])

with mode_col:
    view_mode = st.radio(
        "Отображение",
        ["Обзор", "Моё"],
        horizontal=True,
        label_visibility="collapsed"
    )

with anchor_col:
    show_only_perfume_section = st.checkbox(
        "Духи",
        value=False
    )
search_query = ""

if user_name and "planned_ml" not in st.session_state:
    st.session_state.planned_ml = {}
if "open_row_id" not in st.session_state:
    st.session_state.open_row_id = None

if user_name:
    df_raw = load_data(SHEET_URL)
    v1_df = prepare_v1_dataframe(df_raw, user_name)
    if show_only_perfume_section:
        anchor_index = None

        for idx, row in v1_df.iterrows():
            name = str(row["aroma_name"]).lower()

            if SECTION_ANCHOR_KEYWORD.lower() in name:
                anchor_index = idx
                break

        if anchor_index is not None:
            v1_df = v1_df.iloc[anchor_index:]

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
        "Поиск",
        placeholder="Поиск",
        label_visibility="collapsed"
    ).strip().lower()
    gender_filter = st.selectbox(
        "Пол",
        options=["Все", "жен", "уни", "муж"],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown('</div>', unsafe_allow_html=True)
    generate_message = st.button("📩 Сформировать сообщение")
    if generate_message:
        # 1. Определяем: заказ или добор
        is_reorder = any(v > 0 for v in v1_df["ordered_ml"])

        tags_text = REORDER_TAGS if is_reorder else ORDER_TAGS

        # 2. Собираем позиции из planned_ml
        lines = []

        for _, row in v1_df.iterrows():
            row_id = row["row_id"]
            ml = st.session_state.planned_ml.get(row_id, 0)

            if ml > 0:
                lines.append(f"• {row['aroma_name']} — {ml} мл")

        # 3. Собираем сообщение
        if lines:
            message = (
                    f"{tags_text}\n\n"
                    f"{raw_user_name}\n\n"
                    + "\n".join(lines)
            )

            st.text_area(
                "Сообщение для Telegram",
                value=message,
                height=200
            )
        else:
            st.info("В плане пока нет ароматов для сообщения.")

    if search_query:
        v1_df = v1_df[
            v1_df["aroma_name"]
            .str.lower()
            .str.contains(search_query, na=False)
        ]

    if gender_filter != "Все":
        v1_df = v1_df[v1_df["gender"] == gender_filter]

    for _, row in v1_df.iterrows():
        ordered_ml = int(row["ordered_ml"])
        row_id = row["row_id"]
        planned_ml = st.session_state.planned_ml.get(row_id, 0)

        # 🔥 РЕЖИМ "МОЁ"
        if view_mode == "Моё":
            if ordered_ml == 0 and planned_ml == 0:
                continue  # ← просто пропускаем строку

        price = int(row["price"]) if row["price"] > 0 else None

        # --- базовая подсветка: я это заказала ---
        if ordered_ml > 0:
            bg_color = "#1f3b2d"
        else:
            bg_color = "#0e1117"

        # --- светомузыка (включается вручную в последний день) ---
        if ENABLE_LIGHTSHOW and ordered_ml > 0:
            total_collected = int(row["total_collected"])

            # если всё набрано — тревоги нет
            if total_collected < TOTAL_REQUIRED_ML:
                if CRITICAL_THRESHOLD > 0 and total_collected <= CRITICAL_THRESHOLD:
                    bg_color = "#8b0000"  # CRITICAL
                elif WARNING_THRESHOLD > 0 and total_collected <= WARNING_THRESHOLD:
                    bg_color = "#ff8c00"  # WARNING

        total_my_amount = ordered_ml + planned_ml

        if price is not None:
            right_text = f"{price} ₽ · {total_my_amount}"
        else:
            right_text = f"{total_my_amount}"
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
        if st.button("▾", key=f"open_{row_id}"):
            if st.session_state.open_row_id == row_id:
                st.session_state.open_row_id = None
            else:
                st.session_state.open_row_id = row_id

        if st.session_state.open_row_id == row_id:
            st.markdown("---")

            st.markdown(f"**Набрано:** {row.get('total_collected', '—')}")
            st.markdown(f"**Уже заказано:** {ordered_ml}")
            aroma_name = row["aroma_name"]
            link = f"https://www.fragrantica.ru/search/?q={aroma_name.replace(' ', '%20')}"

            st.markdown(f"[🔗 Fragrantica]({link})")

            col_input, col_info = st.columns([2, 1])

            with col_input:
                current_value = st.session_state.planned_ml.get(row_id, 0)

                new_value = st.number_input(
                    "Количество",
                    min_value=0,
                    value=current_value,
                    step=1,
                    key=f"input_{row_id}",
                )

                if new_value != current_value:
                    st.session_state.planned_ml[row_id] = new_value
                    st.rerun()

            with col_info:
                st.markdown(
                    f"""
                    **План:** {st.session_state.planned_ml.get(row_id, 0)}  
                    **Уже заказано:** {ordered_ml}
                    """
                )


    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.info("Введите имя, чтобы загрузить данные")








