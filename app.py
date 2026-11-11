import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import ee
import json

# ---------------------------------------------------------
# 1. Configuración de Página y Estilos CSS (UI/UX)
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Corredores Vivos",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inyección de CSS para estilizar como Landing Page de Startup
st.markdown("""
    <style>
    /* Colores y tipografía base */
    .stApp { background-color: #fcfcfc; }
    h1, h2, h3 { color: #1e3a1f; font-family: 'Helvetica Neue', sans-serif; }
    
    /* Estilización de las Pestañas */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 55px; 
        background-color: #e8f5e9; 
        border-radius: 8px 8px 0px 0px; 
        padding: 10px 20px;
        font-weight: 600;
        color: #2e7d32;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #2e7d32 !important; 
        color: white !important; 
    }
    
    /* Tarjetas de Métricas */
    div[data-testid="stMetricValue"] { color: #2e7d32; }
    </style>
""", unsafe_allow_html=True)

# Encabezado Principal
st.title("🌱 EcoRastro")
st.markdown("#### Inteligencia Geoespacial para la Red de Corredores Vivos del GORE Santiago")
st.markdown("---")

# ---------------------------------------------------------
# 2. Inicialización Segura de Google Earth Engine
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        if "GCP_SERVICE_ACCOUNT" in st.secrets:
            secret_val = st.secrets["GCP_SERVICE_ACCOUNT"]
            if isinstance(secret_val, str):
                service_account_info = json.loads(secret_val)
            else:
                service_account_info = dict(secret_val)
            
            client_email = service_account_info.get("client_email")
            private_key = service_account_info.get("private_key")
            project_id = service_account_info.get("project_id")
            
            credentials = ee.ServiceAccountCredentials(client_email, key_data=private_key)
            ee.Initialize(credentials, project=project_id)
            return True
        else:
            ee.Initialize()
            return True
    except Exception as e:
        return False

ee_status = init_earth_engine()

# Coordenadas ampliadas para cubrir el Parque O'Higgins
coordenadas_parque = [
    [-70.6678, -33.4530], [-70.6525, -33.4530],
    [-70.6525, -33.4715], [-70.6678, -33.4715], [-70.6678, -33.4530]
]

# Función Satelital (Oculta del Frontend)
def obtener_capa_satelital(capa_tipo):
    if not ee_status: return None, 0.0
    try:
        parque_geometry = ee.Geometry.Polygon(coordenadas_parque)
        coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(parque_geometry).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15)).sort("system:time_start", False)
        imagen = coleccion.first()

        if "Normal" in capa_tipo:
            corte = imagen.select(["B4", "B3", "B2"]).clip(parque_geometry)
            vis_params = {"min": 0, "max": 2500, "gamma": 1.2}
            return corte.getMapId(vis_params)["tile_fetcher"].url_format, 0.0

        elif "NDVI" in capa_tipo:
            corte = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(parque_geometry)
            vis_params = {"min": 0.1, "max": 0.7, "palette": ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]}
        
        elif "NDMI" in capa_tipo:
            ndvi = imagen.normalizedDifference(["B8", "B4"])
            ndmi = imagen.normalizedDifference(["B8A", "B11"])
            corte = ndmi.updateMask(ndvi.gt(0.15)).rename("NDMI").clip(parque_geometry)
            vis_params = {"min": -0.05, "max": 0.3, "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#abd9e9", "#74add1", "#4575b4"]}
            
        elif "NDBI" in capa_tipo:
            corte = imagen.normalizedDifference(["B11", "B8"]).rename("NDBI").clip(parque_geometry)
            vis_params = {"min": -0.2, "max": 0.2, "palette": ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]}

        map_id = corte.getMapId(vis_params)
        mean_stat = corte.reduceRegion(reducer=ee.Reducer.mean(), geometry=parque_geometry, scale=10).getInfo()
        promedio_val = list(mean_stat.values())[0] if mean_stat and list(mean_stat.values())[0] is not None else 0.0
        return map_id["tile_fetcher"].url_format, promedio_val
    except Exception:
        return None, 0.0

# ---------------------------------------------------------
# 3. Estructura de Pestañas (El "Pitch" y el "Dashboard")
# ---------------------------------------------------------
tab_pitch, tab_mapa = st.tabs(["📖 Sobre el Proyecto", "🛰️ Visor Satelital B2G"])

# --- PESTAÑA 1: LANDING PAGE EXPLICATIVA ---
with tab_pitch:
    col1, col2 = st.columns(2)
    with col1:
        st.info("### 🚨 El Problema\nLas ciudades enfrentan el aumento de **Islas de Calor Urbano**. Los municipios invierten en áreas verdes, pero el mantenimiento y riego se realizan a ciegas, desperdiciando recursos hídricos y perdiendo cobertura vegetal crítica por falta de datos en tiempo real.")
    with col2:
        st.success("### 💡 La Solución: EcoRastro\nUna plataforma B2G que traduce datos satelitales (Copernicus) en **acciones tácticas**. Usamos análisis multiespectral para identificar estrés hídrico antes de que sea visible, guiando a las cuadrillas municipales exactamente a las zonas que requieren intervención.")

    st.markdown("### 🗺️ ¿Cómo funciona?")
    col_a, col_b, col_c = st.columns(3)
    col_a.markdown("**1. Escaneo Satelital:**\nSentinel-2 de la Agencia Espacial Europea monitorea la zona con visión infrarroja cada 5 días.")
    col_b.markdown("**2. Procesamiento GEE:**\nNuestra nube filtra cemento y calcula la humedad interna de las hojas mediante el índice NDMI.")
    col_c.markdown("**3. Acción en Terreno:**\nEl operario hace clic en el área crítica y se le genera una ruta GPS directa para intervenir.")
    
    st.markdown("---")
    st.markdown("### 🚀 Roadmap del Proyecto (Desafío GS 2)")
    st.markdown("""
    - ✅ **Fase 1 (MVP Actual):** Visor web satelital B2G para la toma de decisiones estratégicas. Enrutamiento GPS táctico para cuadrillas.
    - ⏳ **Fase 2:** Integración de sensor térmico Landsat 8/9 para cálculo de Temperatura Superficial (LST) e interfaz móvil.
    - 🔮 **Fase 3:** Sistema predictivo con IA para prevenir pérdida de cobertura arbórea y evaluación automática del presupuesto de riego municipal.
    """)

# --- PESTAÑA 2: EL VISOR OPERATIVO (Código intacto pero estilizado) ---
with tab_mapa:
    st.markdown("### Panel de Control Operativo")
    
    # Controles ahora horizontales para mayor elegancia
    capa_seleccionada = st.radio(
        "Filtro de Análisis Multiespectral:",
        ["📸 Normal (RGB)", "🌳 NDVI (Cobertura Vegetal)", "💧 NDMI (Estrés Hídrico)", "🏢 NDBI (Islas de Calor / Cemento)"],
        horizontal=True
    )
    
    # Construcción del Mapa Folium
    m = folium.Map(location=[-33.4625, -70.6588], zoom_start=15, tiles="OpenStreetMap")
    
    plugins.LocateControl(
        position="bottomright", drawCircle=False, keepCurrentZoomLevel=True,
        strings={"title": "Mostrar mi ubicación actual", "popup": "Estás aquí"}
    ).add_to(m)

    tile_url, promedio_val = obtener_capa_satelital(capa_seleccionada)

    if tile_url:
        folium.TileLayer(tiles=tile_url, attr="Copernicus Sentinel-2", name=capa_seleccionada, overlay=True, control=True).add_to(m)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Fuente de Datos", "ESA Sentinel-2 (10m/px)")
        if "Normal" not in capa_seleccionada:
            siglas = capa_seleccionada.split()[1]
            c2.metric(f"Promedio de la Zona ({siglas})", f"{promedio_val:.3f}")
            c3.metric("Estado General", "Requiere Atención" if promedio_val < 0.1 else "Saludable")
        else:
            c2.metric("Tipo de Vista", "Color Verdadero")
            c3.metric("Frecuencia de Paso", "Cada 5 días")
    else:
        folium.Polygon(locations=[[lat, lng] for lng, lat in coordenadas_parque], color="#10b981", fill=True, fill_opacity=0.3).add_to(m)

    # Renderizado y captura de clics
    map_data = st_folium(m, width="100%", height=500, key=capa_seleccionada)

    # Lógica de GPS para Terreno
    if map_data and map_data.get("last_clicked"):
        lat, lng = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
        st.success(f"📍 **Cuadrilla Desplegada** - Coordenadas objetivo: `{lat:.5f}, {lng:.5f}`")
        gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}&travelmode=walking"
        st.markdown(f'<a href="{gmaps_url}" target="_blank" style="display:inline-block; padding:10px 20px; background-color:#1a73e8; color:white; font-weight:bold; border-radius:6px; text-decoration:none;">🚶‍♂️ Iniciar Navegación (Google Maps)</a>', unsafe_allow_html=True)

    with st.expander("📖 Diccionario de Datos Técnicos"):
        st.markdown("""
        * **NDVI:** Mide el vigor de la hoja. Rojo/Naranja = Tierra o vegetación muerta; Verde = Árboles frondosos.
        * **NDMI:** *Capa inteligente (excluye asfalto).* Mide reservas de agua. Rojo = Fuerte déficit hídrico; Azul = Excelente hidratación.
        * **NDBI:** Identifica áreas impermeables. Rojo oscuro = Alta densidad de asfalto (Focos de calor).
        """)
