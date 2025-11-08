import pandas as pd
import itertools
import streamlit as st

github_url = 'https://raw.githubusercontent.com/MJN035/minjun/main/course.csv'
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
        if '(' in s and ')' in s and '~' in s:
            times = s[s.find('(')+1:s.find(')')]
            start, end = times.split('~')
            parsed.append({'day': day, 'start': start, 'end': end})
    return parsed

df['parsed_times'] = df['수업교시'].apply(parse_times)

if 'step' not in st.session_state:
    st.session_state.step = 0
    st.session_state.want_courses = []
    st.session_state.holidays = []
    st.session_state.professor = ''
    st.session_state.consecutive = False
    st.session_state.session_pref = '전체'

st.title('AI 챗봇 시간표 생성기 (9학점 고정, 과목 선택제)')

def advance_chat():
    user = st.chat_input('AI에게 원하는 조건을 입력하세요')
    if user:
        if st.session_state.step == 0:  # 듣고 싶은 과목
            st.session_state.want_courses = [w.strip() for w in user.split(',') if w.strip()]
            st.session_state.step += 1
        elif st.session_state.step == 1:  # 공강 요일
            st.session_state.holidays = [h.strip() for h in user.split(',') if h.strip()]
            st.session_state.step += 1
        elif st.session_state.step == 2:  # 시간대
            if user in ['아침', '오후']:
                st.session_state.session_pref = user
            else:
                st.session_state.session_pref = '전체'
            st.session_state.step += 1
        elif st.session_state.step == 3:  # 교수 및 연강
            st.session_state.professor = user
            st.session_state.step += 1
        elif st.session_state.step == 4:  # 연강 희망
            st.session_state.consecutive = ('예' in user or '연강' in user)
            st.session_state.step += 1

advance_chat()

steps = [
    "듣고 싶은 과목명을 쉼표(,)로 구분해 입력해 주세요.",
    "희망하는 공강 요일을 쉼표(,)로 입력해 주세요. (예: 월,화)",
    "아침/오후 중 원하는 시간대가 있으면 입력(아침/오후), 아니면 엔터",
    "선호하는 교수님 성함을 입력하거나 엔터",
    "연강을 원하는지 입력해주세요. (예: 연강 희망/연강 X)"
]

for i in range(min(st.session_state.step+1, 5)):
    st.chat_message('assistant').write(steps[i])

if st.session_state.step < 5:
    st.info("위 질문에 순서대로 답해주세요. 마지막 답변 후 시간표 추천 결과가 출력됩니다.")
else:
    # 듣고 싶은 과목만 대상으로 필터링
    want_df = df[df['교과목명'].apply(lambda x: any(w in x for w in st.session_state.want_courses))]
    if st.session_state.holidays:
        def has_holiday_conflict(parsed_times, holidays):
            for t in parsed_times:
                if t['day'] in st.session_state.holidays:
                    return True
            return False
        want_df = want_df[~want_df['parsed_times'].apply(lambda x: has_holiday_conflict(x, st.session_state.holidays))]
    if st.session_state.professor:
        want_df = want_df[want_df['주담당교수'].str.contains(st.session_state.professor)]
    if st.session_state.session_pref != '전체':
        def is_session_ok(times, session_pref):
            for t in times:
                h = int(t['start'].split(':')[0])
                if session_pref == '아침' and not (6 <= h < 12):
                    return False
                if session_pref == '오후' and not (12 <= h < 20):
                    return False
            return True
        want_df = want_df[want_df['parsed_times'].apply(lambda x: is_session_ok(x, st.session_state.session_pref))]

    # 시간표 후보 생성 (9학점 초과X, 듣고 싶은 과목만, 조건 모두 적용)
    candidates = want_df.to_dict('records')
    combos = []
    for r in range(1, len(candidates)+1):
        for combo in itertools.combinations(candidates, r):
            total_credit = sum(course['학점'] for course in combo)
            if total_credit > 9:
                continue
            conflict = False
            for i in range(len(combo)):
                for j in range(i+1, len(combo)):
                    def time_conflict(times1, times2):
                        for t1 in times1:
                            for t2 in times2:
                                if t1['day'] == t2['day']:
                                    start1 = int(t1['start'].replace(':',''))
                                    end1 = int(t1['end'].replace(':',''))
                                    start2 = int(t2['start'].replace(':',''))
                                    end2 = int(t2['end'].replace(':',''))
                                    if not (end1 <= start2 or end2 <= start1):
                                        return True
                        return False
                    if time_conflict(combo[i]['parsed_times'], combo[j]['parsed_times']):
                        conflict = True
                        break
                if conflict:
                    break
            if not conflict:
                if st.session_state.consecutive:
                    def is_consecutive(schedule):
                        schedule_by_day = {}
                        for c in schedule:
                            for t in c['parsed_times']:
                                d = t['day']
                                stime = int(t['start'].replace(':',''))
                                etime = int(t['end'].replace(':',''))
                                schedule_by_day.setdefault(d, []).append((stime, etime))
                        for v in schedule_by_day.values():
                            v.sort()
                            gaps = [v[i+1][0] - v[i][1] for i in range(len(v)-1)]
                            if not all(gap <= 100 for gap in gaps if gap >= 0):
                                return False
                        return True
                    if not is_consecutive(combo):
                        continue
                combos.append(combo)
    def score_schedule(schedule):
        return sum(course['학점'] for course in schedule)
    if combos:
        selected = sorted(combos, key=score_schedule, reverse=True)[:5]
        for idx, timetable in enumerate(selected, 1):
            st.chat_message('assistant').markdown(f'**추천 시간표 #{idx} (총 {score_schedule(timetable)}학점)**')
            for course in timetable:
                st.markdown(f"- {course['교과목명']} | 교수: {course['주담당교수']} | {course['학점']}학점")
    else:
        st.chat_message('assistant').warning("조건에 맞는 시간표를 찾지 못했습니다.")
