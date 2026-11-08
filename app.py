import streamlit as st
import folium
from streamlit_folium import st_folium
import numpy as np
import random

# ---------------------------------------------------------
# 1. Configuración de la página & Estilos CSS Personalizados
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Inteligencia Geoespacial Urbana",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS profesionales para mejorar la apariencia por defecto de Streamlit
st.markdown("""
    <style>
    /* Estilo del contenedor principal */
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    
    /* Header estilizado */
    .header-box {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 24px;
        border-radius: 12px;
        border: 1px solid #334155;
        margin-bottom: 24px;
    }
    
    /* Tarjetas de Métricas */
    .metric-card {
        background-color: #1e293b;
        padding: 16px;
        border-radius: 10px;
        border-left: 4px solid #10b981;
        margin-bottom: 12px;
        border-top: 1px solid #334155;
        border-right: 1px solid #334155;
        border-bottom: 1px solid #334155;
    }
    .metric-card.alert {
        border-left-color: #f43f5e;
    }
    .metric-card.info {
        border-left-color: #0284c7;
    }
    .metric-title {
        font-size: 13px;
        color: #94a3b8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 4px;
    }
    .metric-sub {
        font-size: 12px;
        color: #cbd5e1;
        margin-top: 4px;
    }
    
    /* Badge del Estado Satelital */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        background-color: rgba(16, 185, 129, 0.1);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Encabezado / Hero
# ---------------------------------------------------------
st.markdown("""
    <div class="header-box">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span class="status-badge">🛰️ CONEXIÓN SENTINEL-2 ACTIVE</span>
                <h1 style="margin: 8px 0 4px 0; font-size: 30px; font-weight: 800; color: #ffffff;">
                    EcoRastro — Monitoreo Geoespacial Parque O'Higgins
                </h1>
                <p style="color: #94a3b8; margin: 0; font-size: 15px;">
                    Plataforma SaaS de Inteligencia Territorial para Municipalidades y Gestión de Áreas Verdes
                </p>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. Sidebar (Controles e Indicadores)
# ---------------------------------------------------------
st.sidebar.markdown("### ⚙️ Configuración del Análisis")

capa_activa = st.sidebar.radio(
    "Selecciona la capa multiespectral:",
    ("Índice de Salud Vegetal (NDVI)", "Estrés Hídrico (NDWI)")
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📌 Diagnóstico del Parque")

if "NDVI" in capa_activa:
    st.sidebar.markdown("""
        <div class="metric-card">
            <div class="metric-title">Salud General (NDVI)</div>
            <div class="metric-value">0.74 (Óptimo)</div>
            <div class="metric-sub">82% de cobertura con vegetación densa activa.</div>
        </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.markdown("""
        <div class="metric-card alert">
            <div class="metric-title">Estrés Hídrico (NDWI)</div>
            <div class="metric-value">Alerta Sector Norte</div>
            <div class="metric-sub">Zona Fantasilandia requiere riego focalizado urgente.</div>
        </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("""
    <div class="metric-card info">
        <div class="metric-title">Frecuencia de Actualización</div>
        <div class="metric-value">Cada 5 Días</div>
        <div class="metric-sub">Próximo paso orbital: Sentinel-2B</div>
    </div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Diferenciador Clave:** Sustituye catastros manuales estáticos por análisis continuo sin costo de personal en terreno.")

# ---------------------------------------------------------
# 4. Layout Principal (Métricas Superiores + Mapa)
# ---------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("""
        <div class="metric-card">
            <div class="metric-title">Superficie Monitoreada</div>
            <div class="metric-value">79.8 Ha</div>
            <div class="metric-sub">Parque O'Higgins completo</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
        <div class="metric-card">
            <div class="metric-title">Resolución Espacial</div>
            <div class="metric-value">10x10 m</div>
            <div class="metric-sub">Malla de píxeles Sentinel-2</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
        <div class="metric-card">
            <div class="metric-title">Índice Hídrico Global</div>
            <div class="metric-value">-0.12</div>
            <div class="metric-sub">Riesgo moderado por temporada</div>
        </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
        <div class="metric-card alert">
            <div class="metric-title">Zonas de Atención</div>
            <div class="metric-value">2 Sectores</div>
            <div class="metric-sub">Prioridad alta de poda/riego</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 5. Generación del Mapa Satelital Mejorado
# ---------------------------------------------------------
st.markdown("### 🗺️ Visor de Análisis Geoespacial en Tiempo Real")

# Crear el Mapa base con estilo oscuro satelital
m = folium.Map(
    location=[-33.4620, -70.6600], 
    zoom_start=15, 
    tiles="CartoDB dark_matter",
    control_scale=True
)

# Límites del parque para la malla
lat_start, lat_end = -33.4580, -33.4670
lng_start, lng_end = -70.6620, -70.6555
paso = 0.00035 # Píxel más fino (~30 metros)

np.random.seed(42) # Mantener consistencia visual

for lat in np.arange(lat_end, lat_start, paso):
    for lng in np.arange(lng_start, lng_end, paso):
        
        # Excluir la Elipse central y estacionamientos
        if -33.4642 < lat < -33.4608 and -70.6608 < lng < -70.6582:
            continue
            
        if "NDVI" in capa_activa:
            # Paleta de verdes/amarillos para salud vegetal
            val = random.random()
            if val > 0.4:
                color = "#10b981" # Verde sano
                opacity = 0.65
            elif val > 0.2:
                color = "#84cc16" # Verde claro
                opacity = 0.55
            else:
                color = "#eab308" # Estrés amarillo
                opacity = 0.6
        else:
            # Paleta de azul vs rojo/naranja para estrés hídrico
            if lat > -33.4615:
                # Sector Norte (Fantasilandia) -> Estrés hídrico
                color = "#f43f5e" if random.random() > 0.3 else "#fb923c"
                opacity = 0.75
            else:
                # Sector Sur -> Regado
                color = "#0284c7" if random.random() > 0.2 else "#38bdf8"
                opacity = 0.55

        # Dibujar píxeles sin bordes duros
        folium.Rectangle(
            bounds=[[lat, lng], [lat + paso, lng + paso]],
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=opacity,
            weight=0
        ).add_to(m)

# Leyenda en el mapa
st_folium(m, width="100%", height=520)

st.markdown("---")
st.caption("EcoRastro SaaS v2.4 | Prototipo de Validación B2G | Integración de API Google Earth Engine & Sentinel-2")
```eof
