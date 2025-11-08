import pandas as pd
import streamlit as st

github_url = "https://raw.githubusercontent.com/MJN035/minjun/main/강좌검색.csv"

try:
    try:
        df = pd.read_csv(github_url, header=1, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(github_url, header=1, encoding='cp949')
    st.write(df.head())
except Exception as e:
    st.error(f"파일 로딩 중 오류 발생: {e}")
    st.write("접근한 파일 주소:", github_url)
