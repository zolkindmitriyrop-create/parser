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
Вставьте список ИНН — приложение соберёт телефоны, email, адреса и руководителей.
""")

# --- Предупреждение про облачный деплой ---
st.warning("""
⚠️ **Важно:** Если вы видите эту страницу на **Streamlit Cloud / Render / Railway** — 
парсинг **НЕ БУДЕТ РАБОТАТЬ**, так как российские сайты (checko, list-org и др.) 
блокируют запросы с облачных IP-адресов.  
**Решение:** запускайте приложение **локально** на своём компьютере 
(см. инструкцию в README) или используйте **DaData API** (вкладка ниже).
""")

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Настройки")

    use_dadata = st.toggle("🔑 Использовать DaData API", value=False, 
                           help="Работает из любой сети, включая облако. Требует API-ключ.")

    if use_dadata:
        dadata_api_key = st.text_input("DaData API-ключ", type="password",
                                       help="Получите бесплатно на dadata.ru")
        dadata_secret = st.text_input("DaData Secret", type="password")
    else:
        dadata_api_key = None
        dadata_secret = None
        delay = st.slider("Задержка между запросами (сек)", 0.5, 5.0, 1.5, 0.5)

    st.markdown("---")
    st.info("💡 **Совет:** Если сайты блокируют — включите DaData API.")
    st.markdown("---")
    st.markdown("**Источники данных:**")
    st.markdown("- checko.com *(только локально)*")
    st.markdown("- list-org.com *(только локально)*")
    st.markdown("- zachestnyibiznes.ru *(только локально)*")
    st.markdown("- audit-it.ru *(только локально)*")
    st.markdown("- **DaData API** *(работает везде)*")

# --- Main ---
tab1, tab2 = st.tabs(["📝 Ввод вручную", "📁 Загрузка Excel"])

with tab1:
    inn_text = st.text_area(
        "Введите ИНН (по одному на строку):",
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

inn_list = [i.strip() for i in inn_text.split("\n") if i.strip()] if inn_text else []

if st.button("🔍 Начать сбор", type="primary", disabled=len(inn_list) == 0):

    if use_dadata and (not dadata_api_key or not dadata_secret):
        st.error("❌ Введите API-ключ и Secret DaData!")
        st.stop()

    progress_bar = st.progress(0, text="Инициализация...")
    status_text = st.empty()
    log_container = st.empty()
    logs = []

    parser = CompanyParser(
        delay=delay if not use_dadata else 0.5,
        dadata_api_key=dadata_api_key,
        dadata_secret=dadata_secret
    )
    results = []

    for i, inn in enumerate(inn_list):
        progress = (i + 1) / len(inn_list)
        progress_bar.progress(progress, text=f"Обработка {inn}... ({i+1}/{len(inn_list)})")
        status_text.info(f"🔍 Ищем: **{inn}**")

        try:
            data = parser.parse(inn, use_dadata=use_dadata)
            results.append(data)
            src = data.get("Источник", "неизвестно")
            logs.append(f"✅ {inn} — найдено ({src})")
        except Exception as e:
            results.append({
                "ИНН": inn,
                "Название": "",
                "Ошибка": str(e),
                "Статус": "Ошибка",
                "Источник": ""
            })
            logs.append(f"❌ {inn} — ошибка: {e}")

        log_container.code("\n".join(logs[-10:]), language="text")

    progress_bar.empty()
    status_text.empty()

    df_result = pd.DataFrame(results)

    # Статистика
    found = df_result[df_result["Статус"] == "Найдено"].shape[0]
    errors = df_result[df_result["Статус"] == "Ошибка"].shape[0]
    not_found = df_result[df_result["Статус"] == "Не найдено"].shape[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Найдено", found)
    col2.metric("❌ Ошибок", errors)
    col3.metric("⚪ Не найдено", not_found)

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
with st.expander("❓ Почему ничего не находит на Streamlit Cloud?"):
    st.markdown("""
    **Причина:** Российские справочники (checko.com, list-org.com, zachestnyibiznes.ru и др.) 
    блокируют запросы с облачных IP-адресов (Amazon AWS, Google Cloud и т.д.), 
    на которых работают Streamlit Cloud, Render, Railway, Heroku.

    **Решения:**
    1. **Запускать локально** — скачайте репозиторий, `pip install -r requirements.txt`, `streamlit run app.py`.
    2. **Использовать DaData API** — получите бесплатный ключ на [dadata.ru](https://dadata.ru), 
       включите тумблер «Использовать DaData API» в боковой панели. Работает из любой сети.
    3. **Свой VPS в России** — например, Timeweb, Beget. IP будет российский, блокировки не будет.
    """)

st.caption("⚠️ Данные собираются из открытых источников. Актуальность не гарантируется.")
