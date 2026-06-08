import streamlit as st

st.set_page_config(
    page_title="Domain Knowledge Copilot",
    page_icon="DK",
    layout="wide",
)

st.sidebar.title("Navigation")
st.sidebar.radio(
    "Go to",
    options=["Home"],
    index=0,
)

st.title("Domain Knowledge Copilot")
st.write("Frontend skeleton ready.")
