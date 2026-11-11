import streamlit as st
import folium
from streamlit_folium import st_folium
import ee
import json

# ---------------------------------------------------------
# 1. Configuración de Página
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Planificación de Corredores Verdes",
    page_icon="🛰️",
    layout="wide"
)

st.title("🛰️ EcoRastro: Inteligencia Geoespacial & Corredores Verdes")
st.markdown("""
Plataforma B2G de apoyo a la toma de decisiones para la **Municipalidad de Santiago y el GORE**. 
Monitoreo satelital (*Sentinel-2 vía Google Earth Engine*) para la identificación de islas de calor y planificación de infraestructura verde urbana.
""")

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
        st.sidebar.error(f"⚠️ Error GEE: {str(e)}")
        return False

ee_status = init_earth_engine()

# Coordenadas ampliadas para cubrir el Parque O'Higgins y bordes viales
coordenadas_parque = [
    [-70.6678, -33.4530],
    [-70.6525, -33.4530],
    [-70.6525, -33.4715],
    [-70.6678, -33.4715],
    [-70.6678, -33.4530]
]

# ---------------------------------------------------------
# 3. Función de Obtención de Capas Satelitales (Avanzada)
# ---------------------------------------------------------
def obtener_capa_satelital(capa_tipo):
    if not ee_status:
        return None, 0.0

    try:
        parque_geometry = ee.Geometry.Polygon(coordenadas_parque)
        coleccion = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(parque_geometry)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 15))
            .sort("system:time_start", False)
        )
        imagen = coleccion.first()

        if "Normal" in capa_tipo:
            corte = imagen.select(["B4", "B3", "B2"]).clip(parque_geometry)
            vis_params = {"min": 0, "max": 2500, "gamma": 1.2}
            return corte.getMapId(vis_params)["tile_fetcher"].url_format, 0.0

        elif "NDVI" in capa_tipo:
            corte = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI").clip(parque_geometry)
            # Rango más estricto para forzar el contraste entre pasto seco y árbol sano
            vis_params = {"min": 0.1, "max": 0.7, "palette": ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]}
        
        elif "NDMI" in capa_tipo:
            ndvi = imagen.normalizedDifference(["B8", "B4"])
            # ENMASCARAMIENTO: Solo mostramos estrés hídrico donde el NDVI indica que SÍ hay vegetación
            ndmi = imagen.normalizedDifference(["B8A", "B11"])
            corte = ndmi.updateMask(ndvi.gt(0.15)).rename("NDMI").clip(parque_geometry)
            # Paleta de Sequía (Rojo) a Ultra Hidratado (Azul oscuro)
            vis_params = {"min": -0.05, "max": 0.3, "palette": ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#abd9e9", "#74add1", "#4575b4"]}
            
        elif "NDBI" in capa_tipo:
            corte = imagen.normalizedDifference(["B11", "B8"]).rename("NDBI").clip(parque_geometry)
            vis_params = {"min": -0.2, "max": 0.2, "palette": ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]}

        map_id = corte.getMapId(vis_params)
        
        mean_stat = corte.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=parque_geometry,
            scale=10
        ).getInfo()

        if mean_stat and list(mean_stat.values())[0] is not None:
            promedio_val = list(mean_stat.values())[0]
        else:
            promedio_val = 0.0
            
        return map_id["tile_fetcher"].url_format, promedio_val

    except Exception as e:
        st.sidebar.error(f"⚠️ Error procesando capa: {str(e)}")
        return None, 0.0

# ---------------------------------------------------------
# 4. Interfaz de Usuario & Mapa
# ---------------------------------------------------------
st.sidebar.header("⚙️ Filtros Satelitales")
capa_seleccionada = st.sidebar.radio(
    "Selecciona la capa de análisis:",
    [
        "📸 Mapa Normal (RGB)", 
        "🌳 NDVI (Salud Vegetal)", 
        "💧 NDMI (Estrés Hídrico/Humedad)", 
        "🏢 NDBI (Cemento y Asfalto)"
    ]
)

m = folium.Map(
    location=[-33.4625, -70.6588],
    zoom_start=15,
    tiles="OpenStreetMap"
)

tile_url, promedio_val = obtener_capa_satelital(capa_seleccionada)

if tile_url:
    folium.TileLayer(
        tiles=tile_url,
        attr="Google Earth Engine / Copernicus Sentinel-2",
        name=capa_seleccionada,
        overlay=True,
        control=True
    ).add_to(m)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Fuente de Datos", "Sentinel-2 (ESA)")
    col2.metric("Resolución Espacial", "10 metros / píxel")
    
    if "Normal" not in capa_seleccionada:
        siglas = capa_seleccionada.split()[1]
        col3.metric(f"Promedio {siglas}", f"{promedio_val:.3f}")
    else:
        col3.metric("Tipo de Vista", "Color Verdadero")
else:
    if not ee_status:
        st.sidebar.warning("⚠️ Modo Demostración Activo.")
    
    folium.Polygon(
        locations=[[lat, lng] for lng, lat in coordenadas_parque],
        color="#10b981" if "NDVI" in capa_seleccionada else "#38bdf8",
        fill=True,
        fill_opacity=0.3,
        popup="Polígono Objetivo: Parque O'Higgins"
    ).add_to(m)

# El parámetro key asegura que el mapa se actualice al cambiar el filtro
st_folium(m, width="100%", height=550, key=capa_seleccionada)

# ---------------------------------------------------------
# 5. Leyenda y Diccionario de Datos
# ---------------------------------------------------------
st.markdown("---")
with st.expander("📖 Leyenda y Explicación de Indicadores (Haz clic para desplegar)"):
    st.markdown("""
    ### 🌳 NDVI (Índice de Salud Vegetal)
    Mide el vigor, la densidad de las hojas y la capacidad de realizar fotosíntesis. 
    * 🔴 **Rojo / Naranja:** Tierra seca, suelo desnudo o vegetación muerta.
    * 🟡 **Amarillo:** Pasto en mal estado o vegetación muy rala.
    * 🟢 **Verde Oscuro:** Árboles frondosos y pasto muy sano (Alta cobertura de dosel).
    
    ### 💧 NDMI (Índice de Estrés Hídrico)
    *Esta capa usa inteligencia geoespacial para aislar el cemento y analizar **solo la vegetación viva**.*
    * 🔴 **Rojo / Naranja:** Plantas con **fuerte déficit de agua** (Requieren riego priorizado para no morir).
    * 🟡 **Amarillo / Celeste claro:** Nivel de humedad intermedio o normal.
    * 🔵 **Azul Oscuro:** Árboles y áreas con **excelente hidratación** y reservas de agua internas.
    
    ### 🏢 NDBI (Zonas Construidas / Superficies Impermeables)
    Identifica las áreas responsables de generar las "Islas de Calor Urbano".
    * 🟢 **Verde:** Zonas naturales que mitigan la temperatura (sin cemento).
    * 🟡 **Amarillo:** Zonas de uso mixto o suelo compactado.
    * 🔴 **Rojo Oscuro:** Alta densidad de asfalto, hormigón y grandes techos (Focos donde el calor queda atrapado).
    """)

st.caption("EcoRastro B2G | Sistema de Apoyo a la Toma de Decisiones para la Estrategia de Corredores Verdes (GORE / Municipalidad de Santiago).")
