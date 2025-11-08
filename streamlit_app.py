import pandas as pd
import itertools
import streamlit as st

github_url = "https://raw.githubusercontent.com/MJN035/minjun/main/course.csv"

# 첫 2줄 skip하고 컬럼명 제대로 잡기
try:
    df = pd.read_csv(github_url, header=2, encoding='utf-8')
except UnicodeDecodeError:
    df = pd.read_csv(github_url, header=2, encoding='cp949')

cols = ['교과목명', '학점', '학년', '수업교시', '주담당교수']
df = df[cols]
df['학점'] = pd.to_numeric(df['학점'], errors='coerce').fillna(0).astype(int)

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

st.title('시간표 생성기')

max_credit = 9  # 고정

holidays = st.multiselect('희망 공강요일 선택', options=['월','화','수','목','금'])
wants_consecutive = st.checkbox('연강 희망')
professor_pref = st.text_input('희망 교수님 입력')
session_pref = st.radio('수업 시간대 선택', options=['전체', '아침', '오후'])

# 시간표 만들기 버튼
if st.button("시간표 만들기"):
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
    for r in range(2, 6):  # 2~5과목 조합, 1과목은 추천하지 않음
        for combo in itertools.combinations(courses, r):
            total_credit = sum(c['학점'] for c in combo)
            if total_credit > max_credit:
                continue
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

    # 단순 총 학점 최대, 연강/교수 조건 점수 더하면 추천 논리를 고도화할 수 있음
    def score_schedule(schedule):
        score = sum(course['학점'] for course in schedule)
        if wants_consecutive:
            score += 2  # 연강 희망 체크 시 가산점
        return score

    # N개 후보를 점수순으로 보여줌(최대 5개)
    if combos:
        sorted_combos = sorted(combos, key=score_schedule, reverse=True)[:5]
        # 각 시간표를 표로 출력
        for idx, combo in enumerate(sorted_combos, 1):
            st.subheader(f"추천 시간표 #{idx} (총 학점: {sum(c['학점'] for c in combo)})")
            st.table(pd.DataFrame(combo)[['교과목명','주담당교수','학점','수업교시']])
    else:
        st.write("조건에 맞는 시간표를 찾지 못했습니다.")
