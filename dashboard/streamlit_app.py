"""
dashboard/streamlit_app.py
--------------------------
Interactive real-time dashboard for the Public Sanitation Monitoring System.

Run with:
    streamlit run dashboard/streamlit_app.py

Features
--------
- Live sensor metric cards (NH3, H2S, Temperature, Humidity, PM2.5)
- Colour-coded system status indicator
- Interactive time-series trend charts
- Scrollable alert log table
- Cross-location bar chart comparison
- Generate readings on demand or inject anomalies via sidebar
"""

import os
import sys

# Allow imports from the project root regardless of where streamlit is launched
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sanitation Monitor",
    layout="wide",
    page_icon="🏙️",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Lazy imports from project modules
# ---------------------------------------------------------------------------
try:
    from sensor.simulator import SensorSimulator
    from processing.anomaly_detector import AnomalyDetector
    from processing.alert_manager import AlertManager

    _IMPORTS_OK = True
except ImportError as _e:
    _IMPORTS_OK = False
    _IMPORT_ERROR = str(_e)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LOCATIONS = [
    "block_A_toilet_1",
    "block_A_toilet_2",
    "block_B_toilet_1",
    "block_B_toilet_2",
]

SENSOR_META = {
    "nh3_ppm":       {"label": "💨 NH3",          "unit": "ppm",    "icon": "💨"},
    "h2s_ppm":       {"label": "🔶 H2S",           "unit": "ppm",    "icon": "🔶"},
    "temperature_c": {"label": "🌡️ Temperature",   "unit": "°C",     "icon": "🌡️"},
    "humidity_pct":  {"label": "💧 Humidity",       "unit": "%",      "icon": "💧"},
    "pm25_ugm3":     {"label": "🌫️ PM2.5",          "unit": "µg/m³",  "icon": "🌫️"},
}

STATUS_ICONS = {"normal": "🟢", "warning": "🟡", "critical": "🔴"}
STATUS_COLOURS = {"normal": "#2ecc71", "warning": "#f39c12", "critical": "#e74c3c"}

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .main { background-color: #0f1117; }
    .block-container { padding-top: 1.5rem; }
    .stMetric { background: #1e2130; border-radius: 12px; padding: 12px; }
    .status-badge {
        display: inline-block;
        font-size: 1.4rem;
        font-weight: 700;
        padding: 0.4rem 1.2rem;
        border-radius: 20px;
        margin: 0.5rem 0;
    }
    h1, h2, h3 { color: #e8eaf6; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Abort early if imports failed
# ---------------------------------------------------------------------------
if not _IMPORTS_OK:
    st.error(
        f"⚠️ Could not import project modules: `{_IMPORT_ERROR}`\n\n"
        "Make sure you run `streamlit run dashboard/streamlit_app.py` "
        "from the **project root** directory."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "readings" not in st.session_state:
    st.session_state.readings: dict = {loc: [] for loc in LOCATIONS}
if "alerts" not in st.session_state:
    st.session_state.alerts: list = []
if "total_generated" not in st.session_state:
    st.session_state.total_generated: int = 0

# ---------------------------------------------------------------------------
# Shared objects (cached across reruns)
# ---------------------------------------------------------------------------


@st.cache_resource
def get_simulator():
    return SensorSimulator(LOCATIONS)


@st.cache_resource
def get_detector():
    return AnomalyDetector()


@st.cache_resource
def get_alert_manager():
    return AlertManager(alert_log_path="data/alerts.csv")


simulator = get_simulator()
detector = get_detector()
alert_manager = get_alert_manager()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://img.icons8.com/fluency/96/toilet.png",
        width=72,
    )
    st.title("🏙️ Sanitation Monitor")
    st.markdown("---")

    selected_location = st.selectbox(
        "📍 Select Location",
        LOCATIONS,
        format_func=lambda x: x.replace("_", " ").title(),
    )
    time_window = st.slider(
        "📈 History Window (readings)",
        min_value=5,
        max_value=100,
        value=30,
        step=5,
    )
    inject_anomaly = st.toggle("⚠️ Inject Anomaly", value=False)

    st.markdown("---")
    generate_btn = st.button("⚡ Generate New Reading", use_container_width=True)
    batch_btn = st.button("📦 Generate Batch (20)", use_container_width=True)

    st.markdown("---")
    st.markdown(
        f"**Total Readings Generated:** {st.session_state.total_generated}"
    )
    st.markdown(f"**Total Alerts:** {len(st.session_state.alerts)}")

# ---------------------------------------------------------------------------
# Reading generation logic
# ---------------------------------------------------------------------------


def _add_reading(location_id: str, reading: dict) -> None:
    st.session_state.readings[location_id].append(reading)
    st.session_state.total_generated += 1
    history = st.session_state.readings[location_id][:-1]
    result = detector.classify_reading(reading, history)
    if result["status"] != "normal":
        alert = alert_manager.create_alert(location_id, reading, result)
        st.session_state.alerts.append(alert)


if generate_btn:
    reading = simulator.generate_reading(
        selected_location, inject_anomaly=inject_anomaly
    )
    _add_reading(selected_location, reading)

if batch_btn:
    batch = simulator.generate_batch(20, anomaly_rate=0.10 if inject_anomaly else 0.05)
    for r in batch:
        _add_reading(r["location_id"], r)
    st.toast(f"✅ Batch of 20 readings generated across all locations.")

# ---------------------------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------------------------
st.title("🏙️ Public Sanitation Monitoring System")
st.markdown(
    "Real-time IIoT dashboard — MQ-135 · DHT22 · PMS5003 sensors via MQTT"
)
st.markdown("---")

location_readings = st.session_state.readings[selected_location]
current = location_readings[-1] if location_readings else None
prev = location_readings[-2] if len(location_readings) >= 2 else None

# ---------------------------------------------------------------------------
# Row 1: Metric cards
# ---------------------------------------------------------------------------
cols = st.columns(5)
sensor_keys = list(SENSOR_META.keys())

for idx, (key, meta) in enumerate(SENSOR_META.items()):
    with cols[idx]:
        if current:
            val = current.get(key)
            delta = None
            if prev and prev.get(key) is not None and val is not None:
                delta = round(float(val) - float(prev[key]), 2)
            st.metric(
                label=f"{meta['icon']} {key.replace('_', ' ').upper()}",
                value=f"{val:.2f} {meta['unit']}" if val is not None else "N/A",
                delta=delta,
                delta_color="inverse" if key in ("nh3_ppm", "h2s_ppm", "pm25_ugm3") else "normal",
            )
        else:
            st.metric(label=f"{meta['icon']} {key.upper()}", value="—")

# ---------------------------------------------------------------------------
# Row 2: Status indicator
# ---------------------------------------------------------------------------
if current and location_readings:
    history = location_readings[:-1]
    result = detector.classify_reading(current, history)
    status = result["status"]
    icon = STATUS_ICONS.get(status, "⚪")
    colour = STATUS_COLOURS.get(status, "#888")
    method = result.get("method", "threshold")
    confidence = result.get("confidence", 0.0)

    st.markdown(
        f"""
        <div class="status-badge" style="background:{colour}22; border: 2px solid {colour}; color:{colour};">
            {icon} System Status: <strong>{status.upper()}</strong>
            &nbsp;&nbsp;·&nbsp;&nbsp; Method: <em>{method}</em>
            &nbsp;&nbsp;·&nbsp;&nbsp; Confidence: {confidence:.0%}
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.info("📋 No readings yet. Use the sidebar to generate readings.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Row 3: Time-series chart
# ---------------------------------------------------------------------------
st.subheader(
    f"📈 Sensor Trends — {selected_location.replace('_', ' ').title()}"
)

if len(location_readings) >= 2:
    chart_data = pd.DataFrame(location_readings[-time_window:])
    chart_cols = [c for c in sensor_keys if c in chart_data.columns]
    if "timestamp" in chart_data.columns:
        chart_data["timestamp"] = pd.to_datetime(chart_data["timestamp"])
        chart_data = chart_data.set_index("timestamp")

    tab1, tab2, tab3 = st.tabs(["Gas Sensors", "Environmental", "Particulates"])
    with tab1:
        st.line_chart(
            chart_data[["nh3_ppm", "h2s_ppm"]].dropna(),
            height=220,
            use_container_width=True,
        )
    with tab2:
        st.line_chart(
            chart_data[["temperature_c", "humidity_pct"]].dropna(),
            height=220,
            use_container_width=True,
        )
    with tab3:
        st.line_chart(
            chart_data[["pm25_ugm3"]].dropna(),
            height=220,
            use_container_width=True,
        )
else:
    st.info("Generate at least 2 readings to view trend charts.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Row 4: Alert log
# ---------------------------------------------------------------------------
st.subheader("🚨 Alert Log")
col_al, col_ar = st.columns([3, 1])
with col_ar:
    if st.button("🗑️ Clear Alerts"):
        st.session_state.alerts = []
        st.rerun()

if st.session_state.alerts:
    alert_df = pd.DataFrame(st.session_state.alerts)
    display_cols = [
        c for c in ["timestamp", "location_id", "severity", "parameter", "value", "threshold", "message"]
        if c in alert_df.columns
    ]
    st.dataframe(
        alert_df[display_cols].sort_values("timestamp", ascending=False),
        use_container_width=True,
        height=250,
    )
else:
    st.success("✅ No alerts recorded in this session.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Row 5: Location comparison
# ---------------------------------------------------------------------------
st.subheader("📊 Location Comparison (Latest Reading)")
latest_by_loc = {}
for loc in LOCATIONS:
    loc_r = st.session_state.readings[loc]
    if loc_r:
        latest_by_loc[loc] = loc_r[-1]

if latest_by_loc:
    comp_df = pd.DataFrame(latest_by_loc).T
    comp_numeric = comp_df[sensor_keys].astype(float, errors="ignore")
    comp_display = comp_numeric.rename(
        index=lambda x: x.replace("_", " ").title()
    )
    st.bar_chart(comp_display, height=300, use_container_width=True)
else:
    st.info("Generate readings across multiple locations to see this comparison.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption(
    "🏙️ Public Sanitation Monitoring System · "
    "Built with Streamlit · "
    "IIoT + ML Anomaly Detection · "
    "Umesh Pandey © 2025"
)
