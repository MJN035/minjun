import pandas as pd
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

st.title('챗봇 시간표 생성기 (입력 조건 모두 선택 후 계산)')

if 'step' not in st.session_state:
    st.session_state.step = 0
    st.session_state.want_courses = []
    st.session_state.holidays = []
    st.session_state.professor = ''
    st.session_state.consecutive = False
    st.session_state.session_pref = '전체'
    st.session_state.calc_ready = False

questions = [
    "듣고 싶은 과목명을 쉼표(,)로 입력해 주세요.",
    "희망 공강 요일을 쉼표(,)로 입력해 주세요. (월,화 등, 없으면 엔터)",
    "아침/오후 중 원하는 시간대를 입력해 주세요 ('아침', '오후', 없으면 전체)",
    "선호하는 교수님 성함을 입력하거나 엔터",
    "연강만 포함할까요? (예/아니오, 혹은 엔터)"
]

# 입력 인터페이스(챗봇 스타일)
if st.session_state.step < len(questions):
    answer = st.text_input(questions[st.session_state.step], key=f'ans{st.session_state.step}')
    if answer and st.button("다음", key=f'btn_next_{st.session_state.step}'):
        if st.session_state.step == 0:
            st.session_state.want_courses = [x.strip() for x in answer.split(',') if x.strip()]
        elif st.session_state.step == 1:
            st.session_state.holidays = [x.strip() for x in answer.split(',') if x.strip()]
        elif st.session_state.step == 2:
            if answer.strip() in ['아침', '오후']:
                st.session_state.session_pref = answer.strip()
            else:
                st.session_state.session_pref = '전체'
        elif st.session_state.step == 3:
            st.session_state.professor = answer.strip()
        elif st.session_state.step == 4:
            st.session_state.consecutive = ('예' in answer or '연강' in answer)
        st.session_state.step += 1

if st.session_state.step == len(questions):
    st.success("모든 조건 입력 완료! 아래 'AI 시간표 만들기' 버튼을 누르면 결과를 계산합니다.")
    if st.button("AI 시간표 만들기"):
        st.session_state.calc_ready = True

# 시간표 조합/계산은 조건 입력과 버튼 클릭 후에만 실행
if st.session_state.get('calc_ready', False):
    want_df = df[df['교과목명'].apply(lambda x: any(w in x for w in st.session_state.want_courses))]
    if st.session_state.holidays:
        def has_holiday_conflict(parsed_times):
            for t in parsed_times:
                if t['day'] in st.session_state.holidays:
                    return True
            return False
        want_df = want_df[~want_df['parsed_times'].apply(has_holiday_conflict)]
    if st.session_state.professor:
        want_df = want_df[want_df['주담당교수'].str.contains(st.session_state.professor)]
    if st.session_state.session_pref != '전체':
        def is_session_ok(times):
            for t in times:
                h = int(t['start'].split(':')[0])
                pref = st.session_state.session_pref
                if pref == '아침' and not (6 <= h < 12):
                    return False
                if pref == '오후' and not (12 <= h < 20):
                    return False
            return True
        want_df = want_df[want_df['parsed_times'].apply(is_session_ok)]

    courses = want_df.to_dict('records')
    result = []
    def is_conflict(selected, new):
        for s in selected:
            for t1 in s['parsed_times']:
                for t2 in new['parsed_times']:
                    if t1['day'] == t2['day']:
                        st1, et1 = int(t1['start'].replace(':','')), int(t1['end'].replace(':',''))
                        st2, et2 = int(t2['start'].replace(':','')), int(t2['end'].replace(':',''))
                        if not (et1 <= st2 or et2 <= st1):
                            return True
        return False

    def dfs(idx, cur, credit):
        if credit > 9:
            return
        if cur and credit <= 9:
            result.append(cur[:])
        for i in range(idx, len(courses)):
            if not is_conflict(cur, courses[i]):
                dfs(i+1, cur + [courses[i]], credit + courses[i]['학점'])
    dfs(0, [], 0)

    # 연강 조건 필터링
    if st.session_state.consecutive:
        def is_consecutive(schedule):
            by_day = {}
            for c in schedule:
                for t in c['parsed_times']:
                    day = t['day']
                    stime, etime = int(t['start'].replace(':','')), int(t['end'].replace(':',''))
                    by_day.setdefault(day, []).append((stime, etime))
            for slots in by_day.values():
                slots.sort()
                gaps = [slots[i+1][0] - slots[i][1] for i in range(len(slots)-1)]
                if not all(gap <= 100 for gap in gaps if gap >= 0):
                    return False
            return True
        result = [sch for sch in result if is_consecutive(sch)]

    if result:
        result = sorted(result, key=lambda sch: sum(c['학점'] for c in sch), reverse=True)[:5]
        for idx, timetable in enumerate(result, 1):
            st.markdown(f'### 추천 시간표 #{idx} (총 {sum(c["학점"] for c in timetable)} 학점)')
            for course in timetable:
                st.markdown(f"- {course['교과목명']} ({course['주담당교수']} / {course['학점']}학점)")
    else:
        st.warning("조건에 맞는 시간표가 없습니다.")
