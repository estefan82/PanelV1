import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Querybox, Messagebox
import requests
import datetime
import threading
import configparser
import os

CONFIG_FILE = "config.ini"


class WeatherApp(tb.Window):
    def __init__(self):
        super().__init__(
            title="Panel de Control - Hora & Tiempo",
            themename="darkly",
            size=(780, 520),
            resizable=(True, True)
        )

        # Cargar configuración guardada o valores por defecto
        self._load_config()

        self.is_fullscreen = False

        self._apply_vibrant_styles()
        self._build_ui()
        self._update_clock()

        # Eventos para pantalla completa
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)

        # Si tenemos coordenadas guardadas, cargar clima directamente
        if self.lat and self.lon and self.current_city != "Detectando...":
            threading.Thread(target=self._fetch_weather, daemon=True).start()
        elif self.current_city and self.current_city != "Detectando...":
            threading.Thread(target=self._geocode_and_update, args=(self.current_city, False), daemon=True).start()
        else:
            threading.Thread(target=self._init_location_and_weather, daemon=True).start()

    def _load_config(self):
        """Carga las preferencias desde el archivo config.ini."""
        self.config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            self.config.read(CONFIG_FILE)
            self.current_theme = self.config.get("Settings", "theme", fallback="darkly")
            self.current_city = self.config.get("Settings", "city", fallback="Detectando...")
            self.lat = self.config.get("Settings", "lat", fallback=None)
            self.lon = self.config.get("Settings", "lon", fallback=None)
            self.time_font_size = self.config.getint("Settings", "time_font_size", fallback=32)
            self.date_font_size = self.config.getint("Settings", "date_font_size", fallback=11)
            self.weather_font_size = self.config.getint("Settings", "weather_font_size", fallback=22)
        else:
            self.current_theme = "darkly"
            self.current_city = "Detectando..."
            self.lat = None
            self.lon = None
            self.time_font_size = 32
            self.date_font_size = 11
            self.weather_font_size = 22

    def _save_config(self):
        """Guarda las preferencias actuales en el archivo config.ini."""
        if not self.config.has_section("Settings"):
            self.config.add_section("Settings")

        self.config.set("Settings", "theme", self.current_theme)
        self.config.set("Settings", "city", self.current_city)
        if self.lat and self.lon:
            self.config.set("Settings", "lat", str(self.lat))
            self.config.set("Settings", "lon", str(self.lon))
        self.config.set("Settings", "time_font_size", str(self.time_font_size))
        self.config.set("Settings", "date_font_size", str(self.date_font_size))
        self.config.set("Settings", "weather_font_size", str(self.weather_font_size))

        with open(CONFIG_FILE, "w") as configfile:
            self.config.write(configfile)

    def _apply_vibrant_styles(self):
        style = tb.Style()
        style.theme_use(self.current_theme)
        style.configure('TLabel', foreground='#E2E8F0')
        style.configure('primary.TLabel', foreground='#38BDF8')
        style.configure('info.TLabel', foreground='#38BDF8')
        style.configure('secondary.TLabel', foreground='#94A3B8')
        style.configure('TLabelframe.Label', font=('Segoe UI', 10, 'bold'), foreground='#38BDF8')

    def _build_ui(self):
        main_frame = tb.Frame(self, padding=15)
        main_frame.pack(fill=BOTH, expand=YES)

        # -------------------------------------------------------------
        # 1. BARRA SUPERIOR: Selector de Temas + Controles
        # -------------------------------------------------------------
        top_bar = tb.Frame(main_frame)
        top_bar.pack(side=TOP, fill=X, pady=(0, 10))

        tb.Label(
            top_bar,
            text="💡 [F11]: Fullscreen | Haz Clic en cualquier tarjeta para ver opciones",
            font=("Segoe UI", 8),
            bootstyle="secondary"
        ).pack(side=LEFT)

        # Botón Pantalla Completa
        self.btn_fs = tb.Button(
            top_bar,
            text="⛶ Fullscreen",
            bootstyle="info-outline",
            command=self._toggle_fullscreen
        )
        self.btn_fs.pack(side=RIGHT, padx=(5, 0))

        # Desplegable para cambio de tema
        available_themes = ["darkly", "vapor", "pulse", "minty", "journal", "sandstone"]

        self.theme_combo = tb.Combobox(
            top_bar,
            values=available_themes,
            state="readonly",
            width=12
        )
        self.theme_combo.set(self.current_theme)
        self.theme_combo.pack(side=RIGHT, padx=5)
        self.theme_combo.bind("<<ComboboxSelected>>", self._change_theme)

        tb.Label(
            top_bar,
            text="🎨 Tema:",
            font=("Segoe UI", 9, "bold"),
            bootstyle="secondary"
        ).pack(side=RIGHT, padx=(5, 2))

        # -------------------------------------------------------------
        # 3. SECCIÓN INFERIOR: PREVISIÓN A 7 DÍAS
        # -------------------------------------------------------------
        forecast_card = tb.Labelframe(main_frame, text=" 📅 Previsión a 7 Días ", padding=10, bootstyle="info")
        forecast_card.pack(side=BOTTOM, fill=X, pady=(10, 0))

        self.days_container = tb.Frame(forecast_card)
        self.days_container.pack(fill=X, expand=NO)

        self.forecast_day_widgets = []
        for i in range(7):
            day_frame = tb.Frame(self.days_container, padding=(5, 8), bootstyle="secondary")
            day_frame.pack(side=LEFT, fill=X, expand=YES, padx=3)

            lbl_dname = tb.Label(day_frame, text="---", font=("Segoe UI", 9, "bold"), anchor=CENTER)
            lbl_dname.pack(fill=X)

            lbl_dicon = tb.Label(day_frame, text="⏳", font=("Segoe UI Emoji", 20), anchor=CENTER)
            lbl_dicon.pack(fill=X, pady=4)

            lbl_dtemp = tb.Label(day_frame, text="--° / --°", font=("Segoe UI", 9), foreground="#38BDF8", anchor=CENTER)
            lbl_dtemp.pack(fill=X)

            self.forecast_day_widgets.append({
                "name": lbl_dname,
                "icon": lbl_dicon,
                "temp": lbl_dtemp
            })

        # -------------------------------------------------------------
        # 2. SECCIÓN CENTRAL: HORA Y FECHA + CLIMA ACTUAL
        # -------------------------------------------------------------
        top_content = tb.Frame(main_frame)
        top_content.pack(side=TOP, fill=BOTH, expand=YES)

        # --- Tarjeta Izquierda: Hora y Fecha ---
        self.time_card = tb.Labelframe(top_content, text=" 🕒 Hora y Fecha (Haz Clic = Opciones) ", padding=15,
                                       bootstyle="info")
        self.time_card.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 5))
        self.time_card.config(cursor="hand2")

        time_inner_frame = tb.Frame(self.time_card)
        time_inner_frame.pack(expand=YES)

        self.lbl_time = tb.Label(
            time_inner_frame,
            text="00:00:00",
            font=("Consolas", self.time_font_size, "bold"),
            bootstyle="info",
            anchor=CENTER
        )
        self.lbl_time.pack(anchor=CENTER)

        self.lbl_date = tb.Label(
            time_inner_frame,
            text="Cargando fecha...",
            font=("Segoe UI", self.date_font_size, "bold"),
            bootstyle="secondary",
            anchor=CENTER
        )
        self.lbl_date.pack(anchor=CENTER, pady=(4, 0))

        self._bind_click_recursive(self.time_card, lambda e: self._open_time_options())

        # --- Tarjeta Derecha: Clima Actual ---
        self.weather_card = tb.Labelframe(
            top_content,
            text=" 🌤️ Clima Actual (Haz Clic = Opciones) ",
            padding=15,
            bootstyle="primary"
        )
        self.weather_card.pack(side=RIGHT, fill=BOTH, expand=YES, padx=(5, 0))
        self.weather_card.config(cursor="hand2")

        weather_inner_frame = tb.Frame(self.weather_card)
        weather_inner_frame.pack(expand=YES, fill=X)

        self.lbl_city = tb.Label(
            weather_inner_frame,
            text=f"📍 {self.current_city}",
            font=("Segoe UI", 12, "bold"),
            bootstyle="primary"
        )
        self.lbl_city.pack(anchor=W)

        curr_grid = tb.Frame(weather_inner_frame)
        curr_grid.pack(fill=X, pady=8)

        self.lbl_icon = tb.Label(curr_grid, text="⏳", font=("Segoe UI Emoji", 28))
        self.lbl_icon.pack(side=LEFT, padx=(0, 12))

        temp_col = tb.Frame(curr_grid)
        temp_col.pack(side=LEFT, expand=YES, anchor=W)

        self.lbl_temp = tb.Label(temp_col, text="-- °C", font=("Segoe UI", self.weather_font_size, "bold"),
                                 foreground="#38BDF8")
        self.lbl_temp.pack(anchor=W)

        self.lbl_desc = tb.Label(temp_col, text="Consultando...", font=("Segoe UI", 9), bootstyle="secondary")
        self.lbl_desc.pack(anchor=W)

        hum_col = tb.Frame(curr_grid)
        hum_col.pack(side=RIGHT)

        tb.Label(hum_col, text="Humedad", font=("Segoe UI", 8, "bold"), bootstyle="secondary").pack(anchor=E)
        self.lbl_humidity = tb.Label(hum_col, text="-- %", font=("Segoe UI", 15, "bold"), foreground="#4ADE80")
        self.lbl_humidity.pack(anchor=E)

        self._bind_click_recursive(self.weather_card, lambda e: self._open_weather_options())

    def _bind_click_recursive(self, widget, callback):
        widget.bind("<Button-1>", callback)
        for child in widget.winfo_children():
            self._bind_click_recursive(child, callback)

    def _open_time_options(self):
        choice = Messagebox.show_question(
            message="¿Qué deseas ajustar en la sección de Hora y Fecha?",
            title="Opciones - Reloj",
            buttons=["Cambiar Tamaño de Letra:primary", "Cancelar:secondary"],
            parent=self
        )

        if choice == "Cambiar Tamaño de Letra":
            new_size = Querybox.get_integer(
                prompt="Introduce el tamaño de la letra para la Hora:",
                title="Tamaño de Fuente - Hora",
                initialvalue=self.time_font_size,
                minvalue=16,
                maxvalue=72,
                parent=self
            )
            if new_size:
                self.time_font_size = new_size
                self.lbl_time.config(font=("Consolas", self.time_font_size, "bold"))
                self._save_config()

    def _open_weather_options(self):
        choice = Messagebox.show_question(
            message="¿Qué deseas hacer en la sección del Clima?",
            title="Opciones - Clima",
            buttons=["Cambiar Ciudad:primary", "Cambiar Tamaño de Letra:info", "Cancelar:secondary"],
            parent=self
        )

        if choice == "Cambiar Ciudad":
            self._open_city_dialog()
        elif choice == "Cambiar Tamaño de Letra":
            new_size = Querybox.get_integer(
                prompt="Introduce el tamaño de la letra para la Temperatura:",
                title="Tamaño de Fuente - Clima",
                initialvalue=self.weather_font_size,
                minvalue=14,
                maxvalue=60,
                parent=self
            )
            if new_size:
                self.weather_font_size = new_size
                self.lbl_temp.config(font=("Segoe UI", self.weather_font_size, "bold"))
                self._save_config()

    def _open_city_dialog(self):
        city_input = Querybox.get_string(
            prompt="Escribe el nombre de tu ciudad:",
            title="Seleccionar Ciudad",
            initialvalue="" if "Detectando" in self.current_city else self.current_city,
            parent=self
        )

        if city_input:
            threading.Thread(target=self._geocode_and_update, args=(city_input, True), daemon=True).start()

    def _geocode_and_update(self, city_name, save=True):
        self.lbl_desc.config(text="Buscando ciudad...")
        try:
            # Limpiar nombre para la búsqueda (quitar el país si viene en el string)
            clean_search_query = city_name.split(",")[0].strip()
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_search_query}&count=1&language=es&format=json"
            res = requests.get(geo_url, timeout=5).json()

            results = res.get("results")
            if results and len(results) > 0:
                location = results[0]
                self.lat = location.get("latitude")
                self.lon = location.get("longitude")
                city = location.get("name")
                country = location.get("country_code", "").upper()

                self.current_city = f"{city}, {country}" if country else city
                if save:
                    self._save_config()
                self._fetch_weather()
            else:
                self.lbl_desc.config(text="Ciudad no encontrada")
        except Exception:
            self._set_weather_error("Error de búsqueda")

    def _change_theme(self, event=None):
        self.current_theme = self.theme_combo.get()
        style = tb.Style()
        style.theme_use(self.current_theme)
        self._apply_vibrant_styles()
        self._save_config()

    def _toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        if self.is_fullscreen:
            self.btn_fs.config(text="🗗 Restaurar")
        else:
            self.btn_fs.config(text="⛶ Fullscreen")

    def _exit_fullscreen(self, event=None):
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.attributes("-fullscreen", False)
            self.btn_fs.config(text="⛶ Fullscreen")

    def _update_clock(self):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")
        self.lbl_time.config(text=time_str)

        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
                 "Noviembre", "Diciembre"]

        dia_semana = dias[now.weekday()]
        mes = meses[now.month - 1]
        date_str = f"{dia_semana}, {now.day} de {mes}"
        self.lbl_date.config(text=date_str)

        self.after(1000, self._update_clock)

    def _init_location_and_weather(self):
        try:
            res = requests.get("http://ip-api.com/json/", timeout=4).json()
            if res.get("status") == "success":
                detected_city = res.get("city", "Alicante")
                self.current_city = detected_city
                self._geocode_and_update(detected_city, save=True)
            else:
                self._set_weather_error("Ubicación no detectada")
        except Exception:
            self._set_weather_error("Sin conexión IP")

    def _fetch_weather(self):
        if not self.lat or not self.lon:
            return

        try:
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={self.lat}&longitude={self.lon}"
                   "&current=temperature_2m,relative_humidity_2m,weather_code"
                   "&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto")

            res = requests.get(url, timeout=6).json()

            current = res.get("current", {})
            temp = current.get("temperature_2m")
            humidity = current.get("relative_humidity_2m")
            code = current.get("weather_code", 0)
            desc, icon = self._interpret_weather_code(code)

            self.lbl_city.config(text=f"📍 {self.current_city}")
            self.lbl_temp.config(text=f"{round(temp)} °C" if temp is not None else "-- °C")
            self.lbl_humidity.config(text=f"{humidity}%" if humidity is not None else "-- %")
            self.lbl_desc.config(text=desc)
            self.lbl_icon.config(text=icon)

            daily = res.get("daily", {})
            times = daily.get("time", [])
            tmax = daily.get("temperature_2m_max", [])
            tmin = daily.get("temperature_2m_min", [])
            ncodes = daily.get("weather_code", [])

            dias_corto = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

            for i in range(min(7, len(times))):
                date_str = times[i]
                dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")

                day_label = "Hoy" if i == 0 else dias_corto[dt.weekday()]
                _, day_icon = self._interpret_weather_code(ncodes[i] if i < len(ncodes) else 0)
                max_t = round(tmax[i]) if i < len(tmax) and tmax[i] is not None else "--"
                min_t = round(tmin[i]) if i < len(tmin) and tmin[i] is not None else "--"

                widget_set = self.forecast_day_widgets[i]
                widget_set["name"].config(text=day_label)
                widget_set["icon"].config(text=day_icon)
                widget_set["temp"].config(text=f"{max_t}° / {min_t}°")

        except Exception:
            self._set_weather_error("Error al actualizar datos")

    def _set_weather_error(self, message):
        self.lbl_city.config(text=f"📍 {self.current_city}")
        self.lbl_desc.config(text=message)
        self.lbl_temp.config(text="-- °C")
        self.lbl_humidity.config(text="-- %")
        self.lbl_icon.config(text="⚠️")

    @staticmethod
    def _interpret_weather_code(code):
        mapping = {
            0: ("Despejado", "☀️"),
            1: ("Principalmente despejado", "🌤️"),
            2: ("Parcialmente nublado", "⛅"),
            3: ("Nublado", "☁️"),
            45: ("Niebla", "🌫️"),
            48: ("Niebla con escarcha", "🌫️"),
            51: ("Llovizna ligera", "🌦️"),
            53: ("Llovizna moderada", "🌦️"),
            55: ("Llovizna intensa", "🌧️"),
            61: ("Lluvia ligera", "🌧️"),
            63: ("Lluvia moderada", "🌧️"),
            65: ("Lluvia fuerte", "🌧️"),
            71: ("Nieve ligera", "🌨️"),
            73: ("Nieve moderada", "🌨️"),
            75: ("Nieve fuerte", "❄️"),
            80: ("Chubascos ligeros", "🌦️"),
            81: ("Chubascos moderados", "🌧️"),
            82: ("Chubascos violentos", "⛈️"),
            95: ("Tormenta eléctrica", "🌩️"),
            96: ("Tormenta con granizo leve", "⛈️"),
            99: ("Tormenta con granizo fuerte", "⛈️"),
        }
        return mapping.get(code, ("Variable", "🌡️"))

if __name__ == "__main__":
    app = WeatherApp()
    app.mainloop()