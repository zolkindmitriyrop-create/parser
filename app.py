import streamlit as st
import pandas as pd
from parser import CompanyParser
import io

st.set_page_config(
    page_title="Парсер контактов компаний",
    page_icon="📇",
    layout="wide"
)

st.title("📇 Парсер контактов компаний по ИНН")
st.markdown("""
Вставьте список ИНН или ОГРН — приложение соберёт телефоны, email, адреса и руководителей 
из открытых источников (checko, list-org, zachestnyibiznes и др.).
""")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Настройки")
    delay = st.slider("Задержка между запросами (сек)", 0.5, 5.0, 1.0, 0.5)
    max_workers = st.slider("Потоков (параллельных запросов)", 1, 5, 3)
    st.markdown("---")
    st.info("💡 **Совет:** Если сайты блокируют — увеличьте задержку.")
    st.markdown("---")
    st.markdown("**Источники данных:**")
    st.markdown("- checko.com")
    st.markdown("- list-org.com")
    st.markdown("- zachestnyibiznes.ru")
    st.markdown("- audit-it.ru")
    st.markdown("- sbis.ru")

# --- Main ---
tab1, tab2 = st.tabs(["📝 Ввод вручную", "📁 Загрузка Excel"])

with tab1:
    inn_text = st.text_area(
        "Введите ИНН / ОГРН (по одному на строку):",
        height=200,
        placeholder="7703422457\n2311215725\n7702841656"
    )

with tab2:
    uploaded_file = st.file_uploader("Загрузите Excel/CSV с колонкой ИНН", type=["xlsx", "csv"])
    col_name = None
    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            df_upload = pd.read_csv(uploaded_file)
        else:
            df_upload = pd.read_excel(uploaded_file)
        st.write("Превью файла:")
        st.dataframe(df_upload.head(), use_container_width=True)
        col_name = st.selectbox("Выберите колонку с ИНН:", df_upload.columns)
        inn_text = "\n".join(df_upload[col_name].dropna().astype(str).tolist())

# --- Кнопка запуска ---
inn_list = [i.strip() for i in inn_text.split("\n") if i.strip()] if inn_text else []

if st.button("🔍 Начать сбор", type="primary", disabled=len(inn_list) == 0):
    progress_bar = st.progress(0, text="Инициализация...")
    status_text = st.empty()

    parser = CompanyParser(delay=delay, max_workers=max_workers)
    results = []

    for i, inn in enumerate(inn_list):
        progress = (i + 1) / len(inn_list)
        progress_bar.progress(progress, text=f"Обработка {inn}... ({i+1}/{len(inn_list)})")
        status_text.info(f"🔍 Ищем: **{inn}**")

        try:
            data = parser.parse(inn)
            results.append(data)
        except Exception as e:
            results.append({
                "ИНН": inn,
                "Ошибка": str(e),
                "Статус": "Ошибка"
            })

    progress_bar.empty()
    status_text.empty()

    df_result = pd.DataFrame(results)

    st.success(f"✅ Готово! Обработано: {len(results)}")
    st.dataframe(df_result, use_container_width=True, hide_index=True)

    # Excel download
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_result.to_excel(writer, index=False, sheet_name="Результат")
        worksheet = writer.sheets["Результат"]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 60)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    st.download_button(
        label="📥 Скачать Excel",
        data=buffer.getvalue(),
        file_name="company_contacts.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("---")
st.caption("⚠️ Данные собираются из открытых источников. Актуальность не гарантируется. Используйте для предварительной проверки.")


# --- Для деплоя на хостинги, ожидающие WSGI/ASGI ---
# Streamlit не является WSGI-приложением, но некоторые платформы
# требуют экспорта переменной 'app'. Ниже — заглушка для совместимости.
# Для корректной работы используйте: streamlit run app.py

try:
    import streamlit.web.bootstrap as bootstrap
    from streamlit.web.server import Server
    app = st  # экспорт для адаптеров
except Exception:
    app = None
