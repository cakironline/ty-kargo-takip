import streamlit as st
import requests
import base64
from datetime import datetime, timedelta, timezone
import pandas as pd
import os
import json

# ---------------------------------------------------
API_KEY = "BTDnnGqkUveH8tSlGFC4"
API_SECRET = "wwDwc4pXf4J563N1pJww"
SELLER_ID = "107703"

# ---------------------------------------------------
JSON_FILE = "today_orders.json"

# ✅ GÜNLÜK JSON KONTROLÜ (HER GÜN SIFIRLAR)
def today_file_check():
    today = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(JSON_FILE):
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today, "data": []}, f, ensure_ascii=False, indent=2)
        return
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("date") != today:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today, "data": []}, f, ensure_ascii=False, indent=2)

# ✅ KAYITLARI OKU
def load_saved_orders():
    today_file_check()
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f).get("data", [])

# ✅ GÜVENLİ KAYDETME (DUPLICATE ENGELLİ)
def save_orders(new_orders):
    today_file_check()
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    existing = file_data.get("data", [])
    existing_trackers = {o["Tracker Code"] for o in existing if isinstance(o, dict) and "Tracker Code" in o}
    for o in new_orders:
        if isinstance(o, dict) and o.get("Tracker Code") not in existing_trackers:
            existing.append(o)
            existing_trackers.add(o.get("Tracker Code"))
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": datetime.now().strftime("%Y-%m-%d"), "data": existing}, f, ensure_ascii=False, indent=2)
    return existing

# ✅ WAREHOUSE MAP
WAREHOUSE_MAP = {
    7837766: "Ereğli", 7837780: "Karataş", 7623793: "Gazikent", 7507303: "Trabzon",
    7261659: "İpekyolu", 7261658: "Meram", 7837765: "Binevler", 6503006: "TOM",
    6502825: "Sanko", 6502790: "Kampüs", 6502985: "Piazza", 6502771: "Merkez Ayakkabı",
    6502772: "Merkez Giyim", 6502791: "Novada", 7489194: "Fabrika Satış", 6502994: "Oniki Şubat",
    6502797: "Gazimuhtar", 6502816: "Suburcu", 6502789: "BosnaMix", 6502787: "Real",
    6502784: "Plus", 148560: "Aykent Depo", 6502783: "Sportive"
}

# === TRENDYOL AUTH ===
auth_str = f"{API_KEY}:{API_SECRET}"
b64_auth = base64.b64encode(auth_str.encode()).decode()
headers = {
    "Authorization": f"Basic {b64_auth}",
    "Content-Type": "application/json",
    "User-Agent": "Cakir-Kargo-Bot"
}

# === GMT+3 TARİH HESAPLAMA ===
GMT3 = timezone(timedelta(hours=3))
now = datetime.now(GMT3)
start_of_day = datetime(now.year, now.month, now.day, tzinfo=GMT3)
end_of_day = start_of_day + timedelta(days=1)
start_ts = int(start_of_day.timestamp() * 1000)
end_ts = int(end_of_day.timestamp() * 1000)

URL = f"https://apigw.trendyol.com/integration/order/sellers/{SELLER_ID}/orders"

# ✅ GMT+3 uyumlu bugünkü kontrol
def is_today(timestamp_ms):
    dt = datetime.fromtimestamp(timestamp_ms / 1000, GMT3)
    return dt.date() == datetime.now(GMT3).date()

# ✅ MAĞAZA ZİYARETLERİ
def calculate_store_visits(df):
    store_visits = {}
    for _, row in df.iterrows():
        store = row["Mağaza"]
        time_obj = datetime.strptime(row["Kargoya Verilme Zamanı"], "%d-%m-%Y %H:%M:%S")
        if store not in store_visits or time_obj < store_visits[store]:
            store_visits[store] = time_obj
    return store_visits

# ✅ ROZETLİ MAĞAZA KARTLARI
def show_store_cards(store_visits):
    st.subheader("🏬 Mağaza Kargo Uğrama Durumu")
    now_time = datetime.now().time()
    after_15 = now_time >= datetime.strptime("12:00", "%H:%M").time()

    visited, not_visited = [], []

    for code, name in WAREHOUSE_MAP.items():
        if name in store_visits and store_visits[name] is not None:
            visited.append((code, name, store_visits[name]))
        else:
            not_visited.append((code, name))

    visited.sort(key=lambda x: x[2])
    all_cards = visited + [(code, name, None) for code, name in not_visited]

    cols = st.columns(5)

    for i, (code, name, visit_time) in enumerate(all_cards):
        col = cols[i % 5]

        badge_html = f"""
        <span style="
            background:#2c3e50;
            padding:4px 9px;
            border-radius:10px;
            font-size:11px;
            margin-left:6px;
            color:white;">
            {code}
        </span>
        """

        if visit_time is not None:
            time_str = visit_time.strftime('%H:%M:%S')
            col.markdown(f"""
                <div style="background-color:#2ecc71; padding:20px; border-radius:15px; color:white; text-align:center; min-height:150px;">
                    <h4>{name} {badge_html}</h4>
                    <p>Kargo Uğradı ✅</p>
                    <b>{time_str}</b>
                </div>""", unsafe_allow_html=True)
        else:
            shake = "animation:shake 0.5s infinite;" if after_15 else ""
            col.markdown(f"""
                <div style="background-color:#e74c3c; padding:20px; border-radius:15px; color:white; text-align:center; min-height:150px; {shake}">
                    <h4>{name} {badge_html}</h4>
                    <p>Kargo Uğramadı ❌</p>
                </div>""", unsafe_allow_html=True)

    st.markdown("""
    <style>
    @keyframes shake {
        0% { transform: translateX(0px); }
        25% { transform: translateX(4px); }
        50% { transform: translateX(0px); }
        75% { transform: translateX(-4px); }
        100% { transform: translateX(0px); }
    }
    </style>
    """, unsafe_allow_html=True)

# ✅ STREAMLIT
st.set_page_config(layout="wide")
st.title("📦 Günlük Mağaza Kargo Takibi")

if st.button("Siparişleri Çek"):
    with st.spinner("Trendyol verileri çekiliyor..."):
        all_orders_data = []
        page = 0
        size = 200

        while True:
            params = {
                "status": "Shipped",
                "startDate": start_ts,
                "endDate": end_ts,
                "page": page,
                "size": size,
                "orderByField": "PackageLastModifiedDate",
                "orderByDirection": "DESC"
            }

            response = requests.get(URL, headers=headers, params=params)
            if response.status_code != 200:
                st.error(f"Trendyol'dan veri alınamadı (Sayfa {page})")
                st.code(response.text)
                break

            data = response.json()
            orders = data.get("content", [])
            if not orders:
                break

            all_orders_data.extend(orders)
            page += 1

        rows = []

        for o in all_orders_data:

            if o.get("cargoProviderName") != "Trendyol Express Marketplace":
                continue

            
            shipped_time_today = None
            for h in o.get("packageHistories", []):
                if h.get("status") == "Shipped" and is_today(h.get("createdDate")):
                    shipped_time_today = datetime.fromtimestamp(h["createdDate"] / 1000, GMT3).strftime("%d-%m-%Y %H:%M:%S")
                    break

            if not shipped_time_today:
                continue

            order_no = o.get("orderNumber")
            package_id = o.get("shipmentPackageId")
            tracker_code = f"{package_id}_{order_no}"

            warehouse_id = o.get("warehouseId")
            warehouse_name = WAREHOUSE_MAP.get(warehouse_id, "Bilinmeyen Depo")

            rows.append({
                "Tracker Code": tracker_code,
                "Kargoya Verilme Zamanı": shipped_time_today,
                "Mağaza": warehouse_name
            })

        all_orders = save_orders(rows)
        df = pd.DataFrame(all_orders)
        store_visits = calculate_store_visits(df)
        show_store_cards(store_visits)
