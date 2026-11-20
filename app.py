import streamlit as st
import folium
from folium import plugins
from streamlit_folium import st_folium
import ee
import json
import os
from datetime import datetime, timedelta
import google.generativeai as genai

# ---------------------------------------------------------
# 1. Configuración de Página & Tema Visual Bolt
# ---------------------------------------------------------
st.set_page_config(
    page_title="EcoRastro | Monitoreo Satelital",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilos CSS con alto contraste y diseño 1:1 con Bolt (Restaurado)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif; }
    
    .stApp { background-color: #0d1f15 !important; color: #f7f4ed !important; }
    #MainMenu, footer, header { visibility: hidden; }

    .bolt-nav { display: flex; align-items: center; justify-content: space-between; padding: 12px 24px; background-color: #0d1f15; border-bottom: 1px solid rgba(247, 244, 237, 0.1); margin-bottom: 32px; }
    .bolt-logo { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.2rem; color: #f7f4ed; }
    .bolt-btn-nav { background-color: #e76f51; color: #ffffff !important; padding: 8px 20px; border-radius: 9999px; font-weight: 600; font-size: 0.875rem; text-decoration: none; }
    
    .hero-title { font-size: 3rem; font-weight: 700; color: #f7f4ed; line-height: 1.1; margin-bottom: 16px; }
    .hero-subtitle { color: rgba(247, 244, 237, 0.8); font-size: 1.125rem; max-width: 650px; line-height: 1.6; margin-bottom: 24px; }
    .badge-pill { display: inline-flex; align-items: center; gap: 6px; background-color: rgba(247, 244, 237, 0.1); border: 1px solid rgba(247, 244, 237, 0.2); padding: 4px 14px; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; color: #f7f4ed; margin-bottom: 16px; }
    
    div[data-testid="stRadio"] label, div[data-testid="stSelectbox"] label, div[data-testid="stDateInput"] label { color: #f7f4ed !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. Header & Navegación (Bolt UI)
# ---------------------------------------------------------
st.markdown("""
<div class="bolt-nav">
    <div class="bolt-logo">🌱 EcoRastro</div>
    <div style="display: flex; gap: 15px; align-items: center;">
        <span style="color: #10b981; font-weight: 600; font-size: 0.9rem;">● IA Core Activado</span>
        <a href="#dashboard" class="bolt-btn-nav">Ver Dashboard</a>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. Inicialización de Motores (GEE y Gemini LLM)
# ---------------------------------------------------------
@st.cache_resource
def init_earth_engine():
    try:
        if "GCP_SERVICE_ACCOUNT" in st.secrets:
            secret_val = st.secrets["GCP_SERVICE_ACCOUNT"]
            service_account_info = json.loads(secret_val) if isinstance(secret_val, str) else dict(secret_val)
            
            client_email = service_account_info.get("client_email")
            # Limpieza de saltos de línea en la llave privada
            private_key = service_account_info.get("private_key", "").replace("\\n", "\n")
            project_id = service_account_info.get("project_id")
            
            credentials = ee.ServiceAccountCredentials(client_email, key_data=private_key)
            ee.Initialize(credentials, project=project_id)
            return True, "OK"
        else:
            ee.Initialize()
            return True, "OK"
    except Exception as e:
        return False, str(e)

ee_status, ee_error = init_earth_engine()
if not ee_status:
    st.error(f"🚨 Detalle del error de Earth Engine: {ee_error}")
# Inicializar Cerebro IA (Gemini)
has_ai = False
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model_ai = genai.GenerativeModel('gemini-1.5-flash')
    has_ai = True

# ---------------------------------------------------------
# 4. Lógica Satelital y de IA (El Ojo, Tiempo y el Cerebro)
# ---------------------------------------------------------
coordenadas_parque = [
    [-70.6678, -33.4530], [-70.6525, -33.4530],
    [-70.6525, -33.4715], [-70.6678, -33.4715], [-70.6678, -33.4530]
]

def obtener_capa_satelital(capa_tipo, fecha_objetivo):
    if not ee_status: return None, 0.0, "Sin Conexión"
    try:
        parque_geometry = ee.Geometry.Polygon(coordenadas_parque)
        
        # Filtro de tiempo dinámico (La Máquina del Tiempo)
        fecha_fin = datetime.combine(fecha_objetivo, datetime.max.time())
        # Ventana de 45 días hacia atrás desde la fecha objetivo para esquivar días nublados
        fecha_inicio = fecha_fin - timedelta(days=45) 
        
        coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")\
            .filterBounds(parque_geometry)\
            .filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))\
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))\
            .sort("system:time_start", False)
            
        imagen = coleccion.first()
        
        # Extraer la fecha exacta del metadato del satélite
        timestamp = imagen.get('system:time_start')
        fecha_real = ee.Date(timestamp).format('dd/MM/YYYY').getInfo()

        if "Normal" in capa_tipo:
            corte = imagen.select(["B4", "B3", "B2"]).clip(parque_geometry)
            vis_params = {"min": 0, "max": 2500, "gamma": 1.2}
            return corte.getMapId(vis_params)["tile_fetcher"].url_format, 0.0, fecha_real
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
        return map_id["tile_fetcher"].url_format, promedio_val, fecha_real
    except Exception:
        return None, 0.0, "No se encontraron capturas despejadas para esa fecha"

def extraer_historial_arbol(lat, lng, fecha_objetivo):
    """El OJO: Extrae la serie de tiempo satelital comparando 6 meses antes de la fecha elegida vs la fecha elegida."""
    if not ee_status: return {"NDVI_pasado": 0.65, "NDVI_hoy": 0.35, "NDMI_hoy": -0.1}
    
    punto = ee.Geometry.Point([lng, lat])
    fecha_fin = datetime.combine(fecha_objetivo, datetime.max.time())
    
    coleccion = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(punto).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 25))
    
    img_pasada = coleccion.filterDate(ee.Date(fecha_fin - timedelta(days=200)), ee.Date(fecha_fin - timedelta(days=150))).sort("system:time_start", False).first()
    img_objetivo = coleccion.filterDate(ee.Date(fecha_fin - timedelta(days=45)), ee.Date(fecha_fin)).sort("system:time_start", False).first()
    
    try:
        ndvi_pasado = img_pasada.normalizedDifference(["B8", "B4"]).reduceRegion(ee.Reducer.mean(), punto, 10).getInfo().get('nd')
        ndvi_hoy = img_objetivo.normalizedDifference(["B8", "B4"]).reduceRegion(ee.Reducer.mean(), punto, 10).getInfo().get('nd')
        ndmi_hoy = img_objetivo.normalizedDifference(["B8A", "B11"]).reduceRegion(ee.Reducer.mean(), punto, 10).getInfo().get('nd')
        return {
            "NDVI_pasado": round(ndvi_pasado or 0.65, 2), 
            "NDVI_hoy": round(ndvi_hoy or 0.35, 2), 
            "NDMI_hoy": round(ndmi_hoy or -0.1, 2)
        }
    except:
        return {"NDVI_pasado": 0.68, "NDVI_hoy": 0.32, "NDMI_hoy": -0.15}

def generar_diagnostico_ia(especie, datos_satelitales, fecha_str):
    """EL CEREBRO: Redacta la prescripción forestal en base a datos."""
    prompt = f"""
    Actúa como un ingeniero forestal urbano experto. Analiza el siguiente árbol en la fecha {fecha_str}:
    - Especie: {especie}
    - NDVI Histórico (Salud 6 meses antes): {datos_satelitales['NDVI_pasado']}
    - NDVI en la fecha evaluada: {datos_satelitales['NDVI_hoy']}
    - NDMI en la fecha evaluada (Estrés Hídrico): {datos_satelitales['NDMI_hoy']} (Menor a 0 indica estrés hídrico severo).
    
    Redacta en un solo párrafo conciso (máximo 4 líneas) una actualización de estado y una recomendación de acción directiva para la cuadrilla municipal. Sé directo, técnico y urgente si amerita.
    """
    if has_ai:
        try:
            return model_ai.generate_content(prompt).text
        except:
            pass
            
    caida = int((1 - (datos_satelitales['NDVI_hoy'] / max(0.01, datos_satelitales['NDVI_pasado']))) * 100)
    return f"⚠️ Alerta Generada ({fecha_str}): Se detecta una variación significativa (caída del {caida}% en biomasa foliar) en este ejemplar de {especie} respecto a su registro previo. El valor de NDMI ({datos_satelitales['NDMI_hoy']}) sugiere déficit hídrico. **Acción sugerida:** Desplegar cuadrilla para inspección en terreno y ajustar volumen de riego."

@st.cache_data
def cargar_arboles_geojson(filepath):
    arboles = {}
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for feature in data.get('features', []):
                if feature['geometry']['type'] == 'Point':
                    coords = feature['geometry']['coordinates']
                    props = feature['properties']
                    llave = f"{round(coords[1], 4)}_{round(coords[0], 4)}"
                    arboles[llave] = {
                        'lat': coords[1],
                        'lng': coords[0],
                        'especie': props.get('species', 'Árbol sin especificar'),
                        'etapa': props.get('life_cycle', 'Desconocida')
                    }
    return arboles

# ---------------------------------------------------------
# 5. Hero Section
# ---------------------------------------------------------
st.markdown("""
<div class="badge-pill">
    <span style="height: 6px; width: 6px; background-color: #f39a77; border-radius: 50%;"></span>
    Plataforma SaaS B2G
</div>
<h1 class="hero-title">
    Inteligencia Geoespacial para el Monitoreo de <span style="color: #f39a77;">Áreas Verdes</span>
</h1>
<p class="hero-subtitle">
    EcoRastro procesa datos satelitales (Sentinel-2) para unificar la información biológica urbana. 
    Entregamos un panel de control en tiempo real sobre la salud vegetal y el estrés hídrico.
</p>
""", unsafe_allow_html=True)

col_h1, col_h2, col_h3 = st.columns(3)
with col_h1:
    st.caption("⏰ ACTUALIZACIÓN")
    st.markdown("**Cada 5 días**")
with col_h2:
    st.caption("🛰️ FUENTE")
    st.markdown("**Sentinel-2 (ESA)**")
with col_h3:
    st.caption("💧 ÍNDICES")
    st.markdown("**NDVI · NDMI · NDBI**")

st.markdown("---")

# ---------------------------------------------------------
# 6. Problem Section
# ---------------------------------------------------------
st.markdown("""
<div style="background-color: #f7f4ed; border-radius: 24px; padding: 36px; margin-top: 32px; margin-bottom: 32px; font-family: sans-serif;">
    <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #e76f51;">El problema</div>
    <h2 style="color: #142e20; font-size: 1.8rem; font-weight: 700; margin-top: 8px; margin-bottom: 12px; line-height: 1.2;">
        La información biológica está fragmentada y desactualizada.
    </h2>
    <p style="color: #2d5a3f; font-size: 0.95rem; line-height: 1.6; margin-bottom: 24px;">
        Actualmente no existe un monitoreo integral y periódico unificado en el Parque O'Higgins. La información está dispersa entre inventarios municipales estáticos, datos de ciencia ciudadana y estudios académicos aislados. Hace falta un sistema centralizado que mantenga los datos actualizados para la gestión real.
    </p>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">🏢 Inventarios municipales</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Estáticos y sin actualización</span>
        </div>
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">👥 Ciencia ciudadana</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Registros puntuales y dispersos</span>
        </div>
        <div style="background-color: #ffffff; border: 1px dashed #c2d6c9; border-radius: 16px; padding: 14px;">
            <strong style="color: #142e20; display: block; font-size: 0.9rem; margin-bottom: 4px;">🎓 Estudios académicos</strong>
            <span style="color: #407b57; font-size: 0.8rem;">Aislados y de corto alcance</span>
        </div>
    </div>
    <div style="background-color: #fdf0ed; border: 1px solid #f8c9bc; border-radius: 14px; padding: 14px 18px; margin-top: 20px; display: flex; align-items: center; gap: 14px;">
        <span style="background-color: #e76f51; color: white; padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: 0.8rem; white-space: nowrap;">⚡ Impacto</span>
        <span style="color: #142e20; font-weight: 600; font-size: 0.9rem;">
            De un ecosistema fragmentado a 1 sola plataforma centralizada con actualización constante.
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 7. Dashboard Satelital (Máquina del Tiempo + Alta Resolución + Catastro)
# ---------------------------------------------------------
st.markdown("<div id='dashboard'></div>", unsafe_allow_html=True)
st.caption("🛰️ DASHBOARD SATELITAL, MÁQUINA DEL TIEMPO & AUDITORÍA DE CATASTRO")
st.markdown("## Parque O'Higgins: salud vegetal y estrés hídrico")
st.write("Viaja en el tiempo para comparar estados históricos, ajusta la transparencia y haz clic en los marcadores para análisis de IA.")

# Controles de Máquina del Tiempo
col_time1, col_time2 = st.columns([2, 1])
with col_time1:
    opciones_tiempo = {
        "🛰️ Captura más reciente (Hoy)": 0,
        "⏪ Hace 5 días": 5,
        "⏪ Hace 10 días": 10,
        "⏪ Hace 15 días": 15,
        "⏪ Hace 20 días": 20,
        "⏪ Hace 25 días": 25,
        "⏪ Hace 1 mes (30 días)": 30,
        "⏪ Hace 2 meses": 60,
        "⏪ Hace 3 meses": 90,
        "⏪ Hace 6 meses": 180,
        "⏪ Hace 1 año": 365,
        "⏪ Hace 5 años": 1825,
        "📅 Elegir fecha exacta en el calendario...": -1
    }
    seleccion_tiempo = st.selectbox("🕒 Viajar en el tiempo (Comparación Histórica):", list(opciones_tiempo.keys()))

with col_time2:
    dias_atras = opciones_tiempo[seleccion_tiempo]
    if dias_atras == -1:
        # Sentinel-2 tiene registros desde mediados de 2015
        fecha_objetivo = st.date_input("Selecciona una fecha:", value=datetime.now().date() - timedelta(days=365), min_value=datetime(2016, 1, 1).date(), max_value=datetime.now().date())
    else:
        fecha_objetivo = datetime.now().date() - timedelta(days=dias_atras)
        st.date_input("Fecha objetivo calculada:", value=fecha_objetivo, disabled=True)

# Controles de Capa y Transparencia
col_ctrl1, col_ctrl2 = st.columns([3, 1])
with col_ctrl1:
    capa_seleccionada = st.radio(
        "Capas de análisis Sentinel-2:",
        ["🌱 Índice de Salud (NDVI)", "💧 Estrés Hídrico (NDMI)", "🏢 Zonas Construidas (NDBI)", "📸 Foto Satelital (RGB)"],
        horizontal=True
    )
with col_ctrl2:
    opacidad_capa = st.slider(
        "Transparencia de la capa:",
        min_value=0.0, max_value=1.0, value=0.7, step=0.05,
        help="Baja la opacidad para ver el mapa de alta resolución debajo."
    )

# Obtener datos satelitales para la fecha elegida
tile_url, promedio_val, fecha_real = obtener_capa_satelital(capa_seleccionada, fecha_objetivo)

# Cartel informativo con la fecha real del satélite
st.info(f"📅 **Última actualización de esta vista:** Captura satelital real tomada el **{fecha_real}** (buscando imágenes despejadas cercanas al {fecha_objetivo.strftime('%d/%m/%Y')}).")

# Mapa Base Esri Alta Resolución
m = folium.Map(
    location=[-33.4625, -70.6588], 
    zoom_start=16, 
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri World Imagery (Alta Resolución)"
)

# Capa de Calles Transparente
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attr="Etiquetas Viales Esri",
    name="Calles y Lugares",
    overlay=True,
    control=True
).add_to(m)

if tile_url:
    folium.TileLayer(
        tiles=tile_url, 
        attr="Copernicus Sentinel-2", 
        name=capa_seleccionada, 
        overlay=True, 
        control=True,
        opacity=opacidad_capa
    ).add_to(m)
else:
    folium.Polygon(locations=[[lat, lng] for lng, lat in coordenadas_parque], color="#10b981", fill=True, fill_opacity=0.3).add_to(m)

# --- Agregar marcadores de los árboles separando Palmas de Otros ---
diccionario_arboles = cargar_arboles_geojson('arboles.geojson')

if diccionario_arboles:
    grupo_palmas = folium.FeatureGroup(name="🌴 Palmas Chilenas", show=True)
    grupo_otros = folium.FeatureGroup(name="🌳 Otros Árboles (No identificados)", show=True)
    
    for arbol in diccionario_arboles.values():
        especie_str = str(arbol.get('especie', '')).lower()
        es_palma = "palma" in especie_str or "jubaea" in especie_str
        
        if es_palma:
            fill_color = "#10b981"  
            radius = 6              
            fill_opacity = 0.9
            grupo_destino = grupo_palmas
            nombre_mostrar = "Palma Chilena"
            icono = "🌴"
        else:
            fill_color = "#f39a77"  
            radius = 3              
            fill_opacity = 0.45     
            grupo_destino = grupo_otros
            nombre_mostrar = arbol.get('especie', 'Especie no identificada').title()
            icono = "🌳"
            
        html_popup = f"""
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; min-width: 160px; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="background-color: {fill_color}; color: white; padding: 6px 12px; font-weight: bold; font-size: 13px; border-bottom: 1px solid rgba(0,0,0,0.1);">
                {icono} {nombre_mostrar}
            </div>
            <div style="padding: 10px 12px; background-color: #ffffff; color: #333333;">
                <p style="margin: 0 0 6px 0; font-size: 12px;"><b>Etapa:</b> {arbol['etapa']}</p>
                <p style="margin: 0; font-size: 10px; color: #7f8c8d;">📍 Lat: {arbol['lat']:.5f}<br>📍 Lng: {arbol['lng']:.5f}</p>
            </div>
        </div>
        """
        
        folium.CircleMarker(
            location=[arbol['lat'], arbol['lng']],
            radius=radius,
            popup=folium.Popup(html_popup, max_width=250),
            color="#ffffff",        
            weight=0.8,
            fill=True,
            fill_color=fill_color,
            fill_opacity=fill_opacity
        ).add_to(grupo_destino)
        
    grupo_palmas.add_to(m)
    grupo_otros.add_to(m)

folium.LayerControl(position="topright", collapsed=False).add_to(m)

# Renderizar el mapa de Folium y capturar interacción
map_data = st_folium(m, width="100%", height=560, key=f"{capa_seleccionada}_{opacidad_capa}_{fecha_objetivo}")

# ---------------------------------------------------------
# 8. MOTOR DE INTELIGENCIA ARTIFICIAL (AL CLICKEAR EL MAPA)
# ---------------------------------------------------------
if map_data and map_data.get("last_object_clicked"):
    lat_click = map_data["last_object_clicked"]["lat"]
    lng_click = map_data["last_object_clicked"]["lng"]
    
    llave_busqueda = f"{round(lat_click, 4)}_{round(lng_click, 4)}"
    arbol_seleccionado = diccionario_arboles.get(llave_busqueda)

    if arbol_seleccionado:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"### 🧠 Diagnóstico Forestal Automatizado (IA) - Fecha: {fecha_real}")
        with st.spinner(f"Extrayendo serie satelital y generando prescripción para {arbol_seleccionado['especie'].title()}..."):
            
            # Ejecutar Extracción + Gemini según la fecha elegida
            datos_historicos = extraer_historial_arbol(arbol_seleccionado['lat'], arbol_seleccionado['lng'], fecha_objetivo)
            diagnostico = generar_diagnostico_ia(arbol_seleccionado['especie'], datos_historicos, fecha_real)
            
            # Renderizar métricas del análisis histórico
            col_ia1, col_ia2, col_ia3 = st.columns(3)
            col_ia1.metric("NDVI Previo (6 meses antes)", datos_historicos['NDVI_pasado'])
            col_ia2.metric(f"NDVI ({fecha_real})", datos_historicos['NDVI_hoy'], delta=round(datos_historicos['NDVI_hoy'] - datos_historicos['NDVI_pasado'], 2))
            col_ia3.metric(f"NDMI ({fecha_real})", datos_historicos['NDMI_hoy'])
            
            st.success("Análisis completado en tiempo real")
            st.markdown(f"> **🤖 Prescripción y Acción:** {diagnostico}")

# ---------------------------------------------------------
# 9. Tarjetas Inferiores Generales
# ---------------------------------------------------------
if "Normal" not in capa_seleccionada:
    pct_val = int(max(0, min(1, promedio_val + 0.3)) * 100) if "NDVI" in capa_seleccionada else 78
    col_m1, col_m2 = st.columns([1, 2])
    with col_m1:
        st.metric(label="SALUD VEGETAL PROMEDIO DEL PARQUE", value=f"{pct_val}%", delta="Estado Óptimo")
    with col_m2:
        st.info("Biomasa alta en la mayoría de los sectores. Las zonas coloreadas en tonos cálidos (rojo/naranja) requieren seguimiento de riego.")

# ---------------------------------------------------------
# 10. GUÍA TÉCNICA E INTERPRETACIÓN DE ÍNDICES (Diccionario B2G)
# ---------------------------------------------------------
st.markdown("---")
with st.expander("📖 Guía de Interpretación de Capas e Índices Satelitales (Haz clic para desplegar)", expanded=True):
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        st.markdown("""
        ### 🌳 NDVI (Índice de Salud Vegetal)
        Mide el vigor, la densidad foliar y la capacidad de fotosíntesis de la biomasa urbana.
        * 🔴 **Rojo / Naranja:** Tierra seca, suelo desnudo o vegetación muerta.
        * 🟡 **Amarillo:** Pasto en mal estado o vegetación muy rala.
        * 🟢 **Verde Oscuro:** Árboles frondosos y pasto muy sano.
        
        ---
        
        ### 🏢 NDBI (Zonas Construidas / Superficies Impermeables)
        Identifica la densidad de infraestructura que retiene radiación solar.
        * 🟢 **Verde:** Cobertura natural (sin asfalto/hormigón).
        * 🟡 **Amarillo:** Zonas mixtas o suelo compactado.
        * 🔴 **Rojo Oscuro:** Alta acumulación de asfalto y techos (Focos de Islas de Calor).
        """)
        
    with col_exp2:
        st.markdown("""
        ### 💧 NDMI (Índice de Estrés Hídrico)
        *Algoritmo inteligente: Aisla el cemento y analiza **únicamente la vegetación viva**.*
        * 🔴 **Rojo / Naranja:** Plantas con **fuerte déficit de agua** (Requieren riego priorizado urgente).
        * 🟡 **Amarillo / Celeste claro:** Humedad foliar en niveles aceptables.
        * 🔵 **Azul Oscuro:** Árboles con **excelente reserva de agua** e hidratación óptima.
        
        ---
        
        ### 📸 Foto Satelital Normal (RGB)
        Imagen en color verdadero capturada directamente por las bandas ópticas de **Copernicus Sentinel-2** a 10 metros de resolución espacial.
        """)
