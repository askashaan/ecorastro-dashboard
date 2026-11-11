import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import ee
import json

# ---------------------------------------------------------
# 1. Configuración de Página (Diseño Nativo Default)
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Corredores Vivos",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 EcoRastro")
st.subheader("Inteligencia Geoespacial para la Red de Corredores Vivos del GORE Santiago")
st.divider()

# ---------------------------------------------------------
# 2. Inicialización Segura de Google Earth Engine
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        if "GCP_SERVICE_ACCOUNT" in st.secrets:
            secret_val = st.secrets["GCP_SERVICE_ACCOUNT"]
            service_account_info = json.loads(secret_val) if isinstance(secret_val, str) else dict(secret_val)
            
            client_email = service_account_info.get("client_email")
            private_key = service_account_info.get("private_key")
            project_id = service_account_info.get("project_id")
            
            credentials = ee.ServiceAccountCredentials(client_email, key_data=private_key)
            ee.Initialize(credentials, project=project_id)
            return True
        else:
            ee.Initialize()
            return True
    except Exception:
        return False

ee_status = init_earth_engine()

# Coordenadas
coordenadas_parque = [
    [-70.6678, -33.4530], [-70.6525, -33.4530],
    [-70.6525, -33.4715], [-70.6678, -33.4715], [-70.6678, -33.4530]
]

# Función Satelital
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
# 3. Interfaz Limpia (Tabs Nativas)
# ---------------------------------------------------------
tab_pitch, tab_mapa = st.tabs(["📖 Sobre el Proyecto", "🛰️ Visor Operativo"])

with tab_pitch:
    st.markdown("### El Desafío: Islas de Calor Urbano")
    st.write("Las ciudades enfrentan el aumento de temperaturas. Los municipios invierten en áreas verdes, pero el mantenimiento y riego se realizan a ciegas, desperdiciando recursos hídricos y perdiendo cobertura vegetal crítica por falta de datos en tiempo real.")
    
    st.markdown("### La Solución: EcoRastro")
    st.write("Una plataforma B2G que traduce datos satelitales (Copernicus) en **acciones tácticas**. Usamos análisis multiespectral para identificar estrés hídrico antes de que sea visible, guiando a las cuadrillas municipales exactamente a las zonas que requieren intervención.")
    
    st.info("""
    **¿Cómo funciona?**
    1. **Monitoreo:** Sentinel-2 escanea la zona con visión infrarroja.
    2. **Procesamiento:** Google Earth Engine filtra el cemento y calcula la humedad interna de las hojas (NDMI).
    3. **Acción:** El operario selecciona el área crítica y recibe una ruta GPS directa para intervenir.
    """)

with tab_mapa:
    capa_seleccionada = st.radio(
        "Filtro de Análisis Multiespectral:",
        ["📸 Normal (RGB)", "🌳 NDVI (Salud Vegetal)", "💧 NDMI (Estrés Hídrico)", "🏢 NDBI (Islas de Calor / Cemento)"],
        horizontal=True
    )
    
    m = folium.Map(location=[-33.4625, -70.6588], zoom_start=15, tiles="OpenStreetMap")
    
    plugins.LocateControl(
        position="bottomright", drawCircle=False, keepCurrentZoomLevel=True,
        strings={"title": "Mostrar mi ubicación actual", "popup": "Estás aquí"}
    ).add_to(m)

    tile_url, promedio_val = obtener_capa_satelital(capa_seleccionada)

    if tile_url:
        folium.TileLayer(tiles=tile_url, attr="Copernicus Sentinel-2", name=capa_seleccionada, overlay=True, control=True).add_to(m)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Fuente de Datos", "ESA Sentinel-2")
        if "Normal" not in capa_seleccionada:
            siglas = capa_seleccionada.split()[1]
            c2.metric(f"Promedio ({siglas})", f"{promedio_val:.3f}")
            c3.metric("Estado", "Requiere Atención" if promedio_val < 0.1 else "Saludable")
        else:
            c2.metric("Vista", "Color Verdadero")
            c3.metric("Frecuencia", "5 días")
    else:
        folium.Polygon(locations=[[lat, lng] for lng, lat in coordenadas_parque], color="#10b981", fill=True, fill_opacity=0.3).add_to(m)

    map_data = st_folium(m, width="100%", height=500, key=capa_seleccionada)

    if map_data and map_data.get("last_clicked"):
        lat, lng = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
        st.success(f"📍 Coordenadas objetivo: `{lat:.5f}, {lng:.5f}`")
        gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}&travelmode=walking"
        st.markdown(f"[🚶‍♂️ Iniciar Navegación en Google Maps]({gmaps_url})")

    with st.expander("Diccionario de Datos Técnicos"):
        st.write("""
        * **NDVI:** Mide vigor de hoja. Rojo = Tierra/Seco; Verde = Árboles frondosos.
        * **NDMI:** Mide reservas de agua en plantas. Rojo = Déficit hídrico; Azul = Buena hidratación.
        * **NDBI:** Identifica áreas impermeables (cemento/asfalto). Focos de acumulación de calor.
        """)
