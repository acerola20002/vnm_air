import json
import datetime
import re
from FlightRadar24 import FlightRadar24API

fr_api = FlightRadar24API()

CITY_MAP = {
    "Incheon": "인천", "Busan": "부산", "Daegu": "대구", "Cheongju": "청주",
    "Muan": "무안", "Seoul": "서울", "Ho Chi Minh City": "호치민", "Hanoi": "하노이",
    "Nha Trang": "나트랑", "Da Nang": "다낭", "Kaohsiung": "가오슝", "Changi": "싱가포르",
    "Chengdu": "청두", "Macau": "마카오", "Hong Kong": "홍콩",
    "Shanghai": "상하이", "Taipei": "타이베이", "Bangkok": "방콕"
}

IATA_MAP = {
    "MFM": "마카오",
    "HKG": "홍콩",
    "ICN": "인천",
    "PUS": "부산",
    "CXR": "나트랑/깜라인"
}

DOMESTIC_CITIES = [
    "Ho Chi Minh City", "Hanoi", "Da Nang", "Dalat", "Hai Phong",
    "Can Tho", "Phu Quoc", "Vinh", "Hue", "Tuy Hoa"
]

def translate_status(raw_text):
    if not raw_text:
        return "정보없음"

    raw_text = re.sub(r'(dep|arr)\s*\d{2}:\d{2}', '', raw_text, flags=re.IGNORECASE).strip()

    time_match = re.search(r'\d{2}:\d{2}', raw_text)
    time_part = time_match.group() if time_match else ""

    if "Delayed" in raw_text:
        return f"지연 ({time_part})" if time_part else "지연"
    if "Estimated" in raw_text:
        return f"도착예정 ({time_part})" if time_part else "도착예정"
    if "Landed" in raw_text:
        return "도착완료"
    if "Scheduled" in raw_text:
        return "예정"

    return raw_text


def get_time_value(flight_info, mode):
    t_key = 'arrival' if mode == 'arrivals' else 'departure'
    time_data = flight_info.get('time', {})

    t_val = time_data.get('scheduled', {}).get(t_key)
    if not t_val:
        t_val = time_data.get('estimated', {}).get(t_key)

    return t_val


def update_data():
    try:
        now_vn = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)
        now_vn_naive = now_vn.replace(tzinfo=None)

        raw_data = fr_api.get_airport_details("CXR") or {}
        schedule = raw_data.get('airport', {}).get('pluginData', {}).get('schedule', {})

        storage = []

        for mode in ['arrivals', 'departures']:
            data_list = schedule.get(mode, {}).get('data', [])

            for f in data_list:
                flight_info = f.get('flight', {})
                if not flight_info:
                    continue

                port_type = 'origin' if mode == 'arrivals' else 'destination'
                airport_data = flight_info.get('airport', {}).get(port_type, {})

                iata_code = airport_data.get('code', {}).get('iata', '')
                city_raw = airport_data.get('position', {}).get('region', {}).get('city', 'Unknown')

                if city_raw in DOMESTIC_CITIES:
                    continue

                display_city = CITY_MAP.get(city_raw, city_raw)

                if iata_code == "MFM" or "Macau" in city_raw:
                    display_city = "마카오"
                elif iata_code == "HKG" or "Hong Kong" in city_raw:
                    display_city = "홍콩"
                elif iata_code in IATA_MAP:
                    display_city = IATA_MAP[iata_code]

                t_val = get_time_value(flight_info, mode)
                if not t_val:
                    continue

                f_time_vn = datetime.datetime.fromtimestamp(t_val, datetime.timezone.utc) + datetime.timedelta(hours=7)
                f_time_vn_naive = f_time_vn.replace(tzinfo=None)

                if f_time_vn_naive < (now_vn_naive - datetime.timedelta(hours=1)):
                    continue

                date_str = f_time_vn_naive.strftime('%m/%d %H:%M')

                raw_status = flight_info.get('status', {}).get('text', '')

                # ✅ 출발 = 시간 기준
                if mode == 'departures':
                    diff_min = (f_time_vn_naive - now_vn_naive).total_seconds() / 60

                    if diff_min <= 0:
                        kor_status = "출발완료"
                    elif diff_min <= 10:
                        kor_status = "탑승중"
                    elif diff_min <= 30:
                        kor_status = "곧 출발"
                    else:
                        kor_status = "출발예정"
                else:
                    kor_status = translate_status(raw_status)

                storage.append({
                    "type": "도착" if mode == 'arrivals' else "출발",
                    "time": date_str,
                    "timestamp": t_val,
                    "flight": flight_info.get('identification', {}).get('number', {}).get('default', 'N/A'),
                    "city": display_city,
                    "status": kor_status
                })

        if storage:
            final_list = sorted(storage, key=lambda x: x['timestamp'])

            # ⭐ 이 부분이 수정되었습니다.
            update_info = {
                "lastUpdate": now_vn.strftime('%Y-%m-%d %H:%M:%S'),
                "version": int(now_vn.timestamp()),  # 타임스탬프 기반 버전 번호 추가
                "data": final_list
            }

            with open('data.js', 'w', encoding='utf-8') as f:
                f.write(f"const flightInfo = {json.dumps(update_info, ensure_ascii=False, indent=4)};")

            print(f"✅ 업데이트 성공: {now_vn.strftime('%Y-%m-%d %H:%M')}")
            print(f"총 {len(final_list)}개 항공편 저장")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == "__main__":
    update_data()
