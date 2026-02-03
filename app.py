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
SHEET_URL = "https://docs.google.com/spreadsheets/d/1_f7IZpy7AfjO2gw_1DTwjBGq5DO51-sqhlQmgk9fon8/edit?gid=0#gid=0"

# Тексты для сообщений в Telegram
ORDER_TAGS = "#парфюм2"
REORDER_TAGS = "#парфюм2 #добор"

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
 
    .list-container {
    padding-top: 10px;
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
    # ordered_ml и price приводим к числам
    ordered = pd.to_numeric(df["ordered_ml"], errors="coerce").fillna(0)
    price = pd.to_numeric(df["price"], errors="coerce").fillna(0)

    current_sum = (ordered / 10 * price).sum()

    planned_sum = 0.0
    for _, row in df.iterrows():
        row_id = row["row_id"]
        planned_ml = st.session_state.planned_ml.get(row_id, 0)
        planned_sum += (planned_ml / 10) * float(row["price"])

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
raw_user_name = st.text_input(
    "Введите имя (как в закупочном файле):"
)
user_name = normalize_name(raw_user_name)

col1, col2, col3 = st.columns(3)

with col1:
    show_overview = st.checkbox("Обзор", value=True)

with col2:
    show_my = st.checkbox("Моё", value=False)

with col3:
    show_only_perfume_section = st.checkbox("Духи", value=False)
if user_name and "planned_ml" not in st.session_state:
    st.session_state.planned_ml = {}
if "open_row_id" not in st.session_state:
    st.session_state.open_row_id = None

if user_name:
    df_raw = load_data(SHEET_URL)
    v1_df = prepare_v1_dataframe(df_raw, user_name)
    v1_df["ordered_ml"] = pd.to_numeric(
        v1_df["ordered_ml"],
        errors="coerce"
    ).fillna(0)

    if show_my and not show_overview:
        v1_df = v1_df[v1_df["ordered_ml"] > 0]
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
    <div style="font-size:0.9em; line-height:1.2; margin-bottom:6px;">
    <b>{user_name.title()}</b><br>
    Факт: <b>{current_sum:.0f} ₽</b> · План: <b>{planned_sum:.0f} ₽</b>
    </div>
    """,
        unsafe_allow_html=True
    )
    search_query = st.text_input(
        "Поиск",
        placeholder="Поиск",
        label_visibility="collapsed"
    ).strip().lower()
    if search_query:
        v1_df = v1_df[
            v1_df["aroma_name"]
            .str.lower()
            .str.contains(search_query, na=False)
        ]
    generate_message = st.button("Сформировать сообщение")
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

    for _, row in v1_df.iterrows():
        ordered_ml = int(row["ordered_ml"])
        row_id = row["row_id"]
        planned_ml = st.session_state.planned_ml.get(row_id, 0)

        # 🔥 РЕЖИМ "МОЁ"
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

        clicked = st.button(
            f"{row['aroma_name']}    {right_text}",
            key=f"row_{row_id}",
            use_container_width=True,
        )

        if clicked:
            st.session_state.open_row_id = (
                None if st.session_state.open_row_id == row_id else row_id
            )
        if st.session_state.open_row_id == row_id:
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

else:
    st.info("Введите имя, чтобы загрузить данные")








