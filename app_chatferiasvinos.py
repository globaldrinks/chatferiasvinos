import streamlit as st
import os
import time
import pandas as pd
import re
import unicodedata
import requests
from datetime import datetime
from rapidfuzz import process, fuzz

# --- VISIT COUNTER LOGIC ---
COUNTER_FILE = "counter.txt"
if not os.path.exists(COUNTER_FILE):
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        f.write("0")

if "tracked_visit" not in st.session_state:
    st.session_state.tracked_visit = True
    with open(COUNTER_FILE, "r", encoding="utf-8") as f:
        try:
            current_count = int(f.read().strip())
        except ValueError:
            current_count = 0
    new_count = current_count + 1
    with open(COUNTER_FILE, "w", encoding="utf-8") as f:
        f.write(str(new_count))

# --- INITIALIZE SESSION STATE FOR THE TREE ---
if "current_category" not in st.session_state:
    st.session_state.current_category = "main"

# 1. Page Config
st.set_page_config(page_title="Tu Asistente en Meet & Drink", page_icon="🍷")
st.title("🤖 Hola Wine Lover! 🍷")

# 2. Define URL and Load Data
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ebcnXXefMZt6qKf-RieSgKyltnCa9eVKf6GjWiSra4g/edit"

def get_csv_url(url):
    try:
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
        if match:
            sheet_id = match.group(1)
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=MeetDrink"
    except:
        pass
    return None

CSV_URL = get_csv_url(SHEET_URL)

def clean_string(text):
    text = str(text).lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

@st.cache_data(ttl=300)
def load_faqs_tree():
    fallback_df = pd.DataFrame([
        {"category": "main", "question": "🍇 Search by Vineyard", "answer": "TREE_NODE"},
        {"category": "Search by Vineyard", "question": "Viña 1", "answer": "Vino 1"}
    ])
    if not CSV_URL:
        return fallback_df
    try:
        df = pd.read_csv(CSV_URL, storage_options={"timeout": 5})
        df.columns = [str(col).strip().lower() for col in df.columns]
        
        if 'category' in df.columns and 'question' in df.columns and 'answer' in df.columns:
            return df.dropna(subset=['category', 'question'])
        return fallback_df
    except:
        return fallback_df

df_faqs = load_faqs_tree()

# 3. Create/Render Chat History
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "👋 Estoy acá para ayudarte! Explora los vinos presentes en Bocas Moradas o hazme una pregunta directamente."}
    ]

if "waiting_for_email" not in st.session_state:
    st.session_state.waiting_for_email = None

# Renderizar el historial existente primero
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 4. PREDEFINED BUTTONS INTERFACE (DYNAMIC TREE)
st.write("---") 
st.write(f"💡 **Explore Options ({st.session_state.current_category}):**")

button_pressed = None

if not st.session_state.waiting_for_email:
    if st.session_state.current_category != "main":
        if st.button("⬅️ Volver al Menú Principal", use_container_width=True):
            st.session_state.current_category = "main"
            st.rerun()

    # Filtrado por categorías
    current_rows = df_faqs[df_faqs['category'].apply(clean_string) == clean_string(st.session_state.current_category)]
    questions_list = current_rows['question'].tolist()
    
    max_buttons_per_row = 3
    for i in range(0, len(questions_list), max_buttons_per_row):
        row_questions = questions_list[i : i + max_buttons_per_row]
        cols = st.columns(len(row_questions))
        for idx, question in enumerate(row_questions):
            with cols[idx]:
                if st.button(question, key=f"btn_{st.session_state.current_category}_{i+idx}", use_container_width=True):
                    cleaned_q = clean_string(question)
                    is_parent = df_faqs['category'].apply(clean_string).eq(cleaned_q).any()
                    
                    if is_parent:
                        st.session_state.current_category = question
                        st.rerun()
                    else:
                        button_pressed = question
                        
    st.write("")
    if st.button("✨ Quiero más info & Updates de próximos eventos", key="btn_more_info", use_container_width=True):
        button_pressed = "more info"

# 5. CHAT INPUT LOGIC (Cambiado a st.chat_input para mejor UX)
placeholder_text = "Escribe tu email aquí..." if st.session_state.waiting_for_email else "Hazme una pregunta sobre vinos..."
user_typed_input = st.chat_input(placeholder_text)

# Capturar la acción ya sea por botón de arriba o por escritura manual
final_input = None
if button_pressed:
    final_input = button_pressed
elif user_typed_input:
    final_input = user_typed_input

# Procesar la entrada del usuario si existe
if final_input:
    # 1. Agregar inmediatamente el mensaje del usuario al estado
    st.session_state.messages.append({"role": "user", "content": final_input})
    
    # 2. Lógica cuando estamos esperando un Email
    if st.session_state.waiting_for_email:
        user_email = final_input.strip()
        unanswered_question = st.session_state.waiting_for_email
        
        FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSd97qfIqBnK7fy2qKNQJ4t5vauriks29CFy-KXSj6qFGXTsbA/formResponse"
        form_data = {
            "entry.1621915346": user_email,          
            "entry.409076594": unanswered_question   
        }
        try:
            response = requests.post(FORM_URL, data=form_data, timeout=5)
            print(f"--- Google Form Status: {response.status_code} ---") 
        except Exception as e:
            print(f"--- Form Submission Error: {str(e)} ---")
            with open("leads_log.txt", "a", encoding="utf-8") as f:
                f.write(f"Date: {datetime.now()} | Email: {user_email} | Question: {unanswered_question} (Form Fail)\n")
            
        bot_response = "¡Gracias! Nos contactaremos contigo por correo a la brevedad. ¡Disfruta la feria! 🍷"
        st.session_state.waiting_for_email = None

    # 3. Lógica Normal de preguntas / solicitud de info
    else:
        clean_input = clean_string(final_input)
        
        if "more info" in clean_input or clean_input == "info":
            bot_response = "¡Con gusto te enviaremos más información! Por favor, escribe tu email aquí abajo."
            st.session_state.waiting_for_email = "Requested General More Info"
                
        else:
            all_questions = df_faqs['question'].tolist()
            # Búsqueda difusa segura contra nulos (None)
            best_match = process.extractOne(clean_input, [clean_string(q) for q in all_questions], scorer=fuzz.WRatio, score_cutoff=60)
                    
            if best_match is not None: # El fix crítico para evitar el crash
                matched_index = best_match[2]
                bot_response = df_faqs.iloc[matched_index]['answer']
            else:
                bot_response = f"Ups, no tengo una respuesta exacta para '{final_input}', pero si me dejas tu email, te responderemos en privado a la brevedad."
                st.session_state.waiting_for_email = final_input

    # Agregar respuesta del bot y recargar la página para mostrar los cambios
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
    st.rerun()

# 6. SECRET ADMIN PANEL
st.write("---")
with st.expander("🔒 Admin Panel (Leads & Stats)"):
    password = st.text_input("Enter Admin Password:", type="password")
    if password == "mysecret123":
        with open(COUNTER_FILE, "r", encoding="utf-8") as f:
            total_visits = f.read().strip()
        st.write(f"📈 **Total Website Visits:** `{total_visits}`")
