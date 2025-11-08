import pandas as pd
import itertools
import streamlit as st

# 0. Github raw CSV url(꼭 raw로 시작하고, 'blob' 대신 'raw'로 입력)
github_url = "https://raw.githubusercontent.com/MJN035/minjun/main/강좌검색.csv"

# 1. 데이터 파싱 및 전처리 - 인코딩 오류 예외 처리
try:
    df = pd.read_csv(github_url, header=1, encoding='utf-8')
except UnicodeDecodeError:
    df = pd.read_csv(github_url, header=1, encoding='cp949')

# 필요한 컬럼만 추출 
cols = ['교과목명', '학점', '학년', '수업교시', '주담당교수']
df = df[cols]
df['학점'] = pd.to_numeric(df['학점'], errors='coerce').fillna(0).astype(int)

# 수업시간(요일, 시간) 파싱 함수
def parse_times(times_str):
    if pd.isna(times_str):
        return []
    sessions = times_str.split('/')
    parsed = []
    for s in sessions:
        day = s[0]
        times = s[s.find("(")+1:s.find(")")]
        start, end = times.split('~')
        parsed.append({'day': day, 'start': start, 'end': end})
    return parsed

df['parsed_times'] = df['수업교시'].apply(parse_times)

# 2. Streamlit UI
st.title('시간표 생성기')
max_credit = st.slider('수강최대학점', min_value=1, max_value=21, value=9)
holidays = st.multiselect('희망 공강요일 선택', options=['월','화','수','목','금'])
wants_consecutive = st.checkbox('연강 희망')
professor_pref = st.text_input('희망 교수님 입력')
session_pref = st.radio('수업 시간대 선택', options=['전체', '아침', '오후'])

# 3. 조건별 과목 필터링
filtered_df = df[df['학점'] <= max_credit]

if holidays:
    def has_holiday_conflict(parsed_times, holidays):
        for t in parsed_times:
            if t['day'] in holidays:
                return True
        return False
    filtered_df = filtered_df[~filtered_df['parsed_times'].apply(lambda x: has_holiday_conflict(x, holidays))]

if professor_pref:
    filtered_df = filtered_df[filtered_df['주담당교수'].str.contains(professor_pref)]

if session_pref != '전체':
    def is_session_ok(times, session_pref):
        for t in times:
            h = int(t['start'].split(':')[0])
            if session_pref == '아침' and not (6 <= h < 12):
                return False
            if session_pref == '오후' and not (12 <= h < 20):
                return False
        return True
    filtered_df = filtered_df[filtered_df['parsed_times'].apply(lambda x: is_session_ok(x, session_pref))]

# 4. 시간표 후보 조합(중복 없는 조합 탐색)
def time_conflict(times1, times2):
    for t1 in times1:
        for t2 in times2:
            if t1['day'] == t2['day']:
                start1 = int(t1['start'].replace(':', ''))
                end1 = int(t1['end'].replace(':', ''))
                start2 = int(t2['start'].replace(':', ''))
                end2 = int(t2['end'].replace(':', ''))
                if not (end1 <= start2 or end2 <= start1):
                    return True
    return False

courses = filtered_df.to_dict('records')
combos = []
for r in range(1, 6):  # 조합 최댓값은 필요에 따라 조정
    for combo in itertools.combinations(courses, r):
        conflict = False
        for i in range(len(combo)):
            for j in range(i + 1, len(combo)):
                if time_conflict(combo[i]['parsed_times'], combo[j]['parsed_times']):
                    conflict = True
                    break
            if conflict:
                break
        if not conflict:
            combos.append(combo)

# 5. AI 기반 시간표 제안(여기선 총 학점 높은 조합 추천)
def score_schedule(schedule):
    return sum(course['학점'] for course in schedule)

if combos:
    best_schedule = max(combos, key=score_schedule)
    st.write("추천 시간표 (총 학점:", score_schedule(best_schedule), ")")
    for course in best_schedule:
        st.write(f"{course['교과목명']} - {course['주담당교수']} - {course['학점']}학점")
else:
    st.write("조건에 맞는 시간표를 찾지 못했습니다.")
