"""Genera los presupuestos en PDF (modelo de optimización y agente de IA).

Uso:  python tools/make_proposals.py
Salida:  proposals/*.pdf
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "proposals"

# Paleta
INK = (23, 30, 40)
ACCENT = (37, 99, 235)
MUTED = (110, 120, 135)
GOOD = (22, 130, 80)
LIGHT = (243, 246, 250)

_REPL = {
    "→": "->", "≈": "aprox. ", "–": "-", "—": "-", "•": "-", "…": "...",
    "“": '"', "”": '"', "‘": "'", "’": "'", "±": "+/-", "·": "-", "€": "EUR",
}


def s(text: str) -> str:
    for k, v in _REPL.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


class Proposal(FPDF):
    def __init__(self, title: str, subtitle: str):
        super().__init__(format="A4")
        self.title_text = title
        self.subtitle_text = subtitle
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 16, 18)
        self.add_page()

    # --- chrome --------------------------------------------------------- #
    def header(self):
        self.set_fill_color(*ACCENT)
        self.rect(0, 0, 210, 6, "F")
        if self.page_no() == 1:
            self.set_xy(18, 14)
            self.set_text_color(*MUTED)
            self.set_font("Helvetica", "B", 9)
            self.cell(0, 5, s("PROPUESTA COMERCIAL"))
            self.ln(7)
            self.set_text_color(*INK)
            self.set_font("Helvetica", "B", 20)
            self.multi_cell(0, 8, s(self.title_text))
            self.ln(1)
            self.set_text_color(*ACCENT)
            self.set_font("Helvetica", "", 11)
            self.multi_cell(0, 6, s(self.subtitle_text))
            self.ln(2)
            self.set_draw_color(225, 230, 236)
            self.line(18, self.get_y(), 192, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "", 8)
        self.cell(0, 5, s("Servicios Megabytes, C.A.  -  Preparado por Omar Moya"))
        self.set_x(-30)
        self.cell(12, 5, s(f"Pag. {self.page_no()}"), align="R")

    # --- bloques -------------------------------------------------------- #
    def meta(self, rows: list[tuple[str, str]]):
        self.set_font("Helvetica", "", 10)
        for k, v in rows:
            self.set_text_color(*MUTED)
            self.cell(34, 6, s(k))
            self.set_text_color(*INK)
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 6, s(v), ln=1)
            self.set_font("Helvetica", "", 10)
        self.ln(3)

    def section(self, title: str):
        self.ln(2)
        self.set_text_color(*ACCENT)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 7, s(title), ln=1)
        self.set_draw_color(225, 230, 236)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(2)
        self.set_text_color(*INK)

    def para(self, text: str):
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(*INK)
        self.multi_cell(0, 5.6, s(text))
        self.ln(1)

    def bullet(self, text: str, bold_lead: str = ""):
        x0 = self.get_x()
        y0 = self.get_y()
        self.set_fill_color(*ACCENT)
        self.rect(x0 + 1, y0 + 2.2, 1.8, 1.8, "F")
        self.set_x(x0 + 6)
        if bold_lead:
            self.set_font("Helvetica", "B", 10.5)
            self.set_text_color(*INK)
            lead_w = self.get_string_width(s(bold_lead) + " ")
            self.cell(lead_w, 5.6, s(bold_lead))
            self.set_font("Helvetica", "", 10.5)
            self.multi_cell(0, 5.6, s(text))
        else:
            self.set_font("Helvetica", "", 10.5)
            self.set_text_color(*INK)
            self.multi_cell(0, 5.6, s(text))
        self.ln(0.6)

    def price_row(self, concept: str, amount: str, note: str = "", highlight=False):
        h = 9
        x0, y0 = 18, self.get_y()
        if highlight:
            self.set_fill_color(*LIGHT)
            self.rect(x0, y0, 174, h, "F")
        self.set_xy(x0 + 3, y0)
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B" if highlight else "", 10.5)
        self.cell(96, h, s(concept))
        self.set_text_color(*ACCENT if highlight else INK)
        self.set_font("Helvetica", "B", 11)
        self.cell(34, h, s(amount), align="R")
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "", 8.5)
        self.set_xy(x0 + 3, y0 + h - 0.5)
        self.set_y(y0 + h)
        if note:
            self.set_x(x0 + 3)
            self.set_text_color(*MUTED)
            self.set_font("Helvetica", "", 8.5)
            self.multi_cell(174, 4.6, s(note))
        self.ln(1)

    def callout(self, text: str):
        self.ln(1)
        x0, y0 = 18, self.get_y()
        self.set_fill_color(*LIGHT)
        self.set_draw_color(*ACCENT)
        self.set_font("Helvetica", "", 10)
        self.set_xy(x0 + 4, y0 + 3)
        self.set_text_color(*INK)
        # medir alto aproximado
        self.multi_cell(166, 5.4, s(text))
        y1 = self.get_y()
        self.rect(x0, y0, 1.6, y1 - y0 + 3, "F")  # barra de acento
        self.ln(3)


def build_model_proposal() -> Path:
    today = dt.date.today().strftime("%d/%m/%Y")
    p = Proposal(
        "Modelo de Simulacion y Optimizacion de Mezclas RAEE",
        "Inteligencia de mezcla para maximizar el rendimiento del material",
    )
    p.meta([
        ("Cliente:", "Servicios Megabytes, C.A. (Gilberto)"),
        ("Preparado por:", "Omar Moya"),
        ("Fecha:", today),
        ("Validez:", "30 dias"),
    ])

    p.section("1. Resumen")
    p.para(
        "Sistema que simula y optimiza las mezclas de chatarra electronica (RAEE) "
        "que se envian a la refineria, replicando con exactitud su formula de "
        "valorizacion. El foco es el RENDIMIENTO del material: cuanto metal se "
        "recupera de cada pila y como combinarlas para que la refineria pague lo "
        "maximo, sin diluir el oro con relleno pobre."
    )

    p.section("2. Alcance funcional")
    p.bullet("simula una mezcla y muestra al instante la ley, la recuperacion (RR) y el resultado.", "Simulador en vivo:")
    p.bullet("arma solo las mezclas mas rentables y explica por que cada decision.", "Optimizador automatico:")
    p.bullet("editar o cargar el stock desde Excel; queda persistido y lo usan todos los modulos.", "Inventario en tiempo real:")
    p.bullet("cada lote real contra su mezcla optima, con el calculo a la vista, paso a paso.", "Historico:")
    p.bullet("leyes despejadas del historico, validadas contra el pago real de la refineria.", "Estimacion de leyes:")
    p.bullet("los materiales se muestran por numero (no se filtran las formulas ni el know-how).", "Modo confidencial:")
    p.bullet("desplegado en el servidor del cliente, con acceso web desde PC y telefono.", "Implementacion:")

    p.section("3. Valor para el negocio")
    p.bullet("reproduce el pago real de la refineria con un desvio de solo +/-3%.", "Fiel a la realidad:")
    p.bullet("predice el rendimiento de cada lote y prioriza los mas rentables.", "Prediccion:")
    p.bullet("detecta plata y paladio que hoy paga $0 por quedar bajo el umbral, para rescatarlo mezclando.", "Rescate de metal:")
    p.bullet("pone en valor 15 pilas de inventario que hoy no tienen datos, con un piso conservador de mercado.", "Inventario dormido:")
    p.bullet("decisiones en segundos y auditables, en vez de planillas a mano.", "Velocidad y control:")

    p.section("4. Inversion")
    p.price_row("Construccion e implementacion", "$2.500", "Pago unico. Despliegue, carga de datos reales, validacion y capacitacion.", highlight=True)
    p.price_row("Mensualidad", "$300 / mes", "Hosting, soporte, actualizaciones y mejoras del modelo.")
    p.price_row("Fee de exito", "5%", "Sobre el rendimiento extra DOCUMENTADO que genere el modelo frente a la practica actual.", highlight=True)
    p.callout(
        "ROI: sobre un volumen anual del orden de los 3 millones de USD que pasan por "
        "la refineria, el costo del sistema representa una fraccion minima. Una sola "
        "mezcla mejor armada, o un lote sub-umbral rescatado, ya cubre el ano."
    )

    p.section("5. Condiciones y proximos pasos")
    p.bullet("El fee de exito se liquida sobre mejoras medibles y acordadas con el cliente.")
    p.bullet("Las leyes estimadas se reemplazan por ensayos de laboratorio a medida que esten disponibles.")
    p.bullet("Precios en USD. La mensualidad se factura por adelantado.")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "Propuesta_Modelo_Optimizacion_RAEE.pdf"
    p.output(str(path))
    return path


def build_agent_proposal() -> Path:
    today = dt.date.today().strftime("%d/%m/%Y")
    p = Proposal(
        "Agente de IA para Servicios Megabytes",
        "Automatizacion de comunicacion, atencion y gestion del negocio",
    )
    p.meta([
        ("Cliente:", "Servicios Megabytes, C.A. (Gilberto)"),
        ("Preparado por:", "Omar Moya"),
        ("Fecha:", today),
        ("Validez:", "30 dias"),
    ])

    p.section("1. Resumen")
    p.para(
        "Agente de inteligencia artificial que automatiza la comunicacion, la "
        "atencion al cliente y la gestion operativa del negocio, integrado al "
        "modelo de simulacion y optimizacion. Funciona como un asistente que "
        "trabaja 24/7: informa, atiende, busca oportunidades y vigila el inventario."
    )

    p.section("2. Alcance funcional")
    p.bullet("genera y envia reportes a Gilberto y su socio por WhatsApp.", "Reportes automaticos:")
    p.bullet("atiende consultas de clientes por WhatsApp, correo electronico y redes sociales.", "Atencion al cliente:")
    p.bullet("busca y capta posibles clientes y proveedores de material.", "Captacion:")
    p.bullet("hace seguimiento del inventario y genera alertas (stock, oportunidades, vencimientos).", "Inventario y alertas:")
    p.bullet("se conecta al modelo de optimizacion para buscar material que mejore los lotes (mejores mezclas).", "Integracion con el modelo:")
    p.bullet("lee e interpreta reportes y KPIs del personal para resumirlos a la direccion.", "KPIs del personal:")

    p.section("3. Beneficios")
    p.bullet("responde al instante y no deja clientes sin atender.")
    p.bullet("convierte datos dispersos (correo, chat, inventario) en decisiones y alertas.")
    p.bullet("conecta la parte comercial con la tecnica: busca el material que falta para armar mejores lotes.")

    p.section("4. Inversion")
    p.price_row("Construccion del agente", "$750", "Pago unico. Diseno, integraciones y puesta en marcha.", highlight=True)
    p.price_row("Mensualidad", "$250 / mes", "Operacion, mantenimiento, ajustes y soporte.", highlight=True)
    p.callout(
        "Las integraciones con WhatsApp, correo y redes requieren las cuentas y "
        "permisos del cliente (p. ej. WhatsApp Business API). El alcance puede "
        "crecer por fases segun prioridades."
    )

    p.section("5. Proximos pasos")
    p.bullet("Definir el primer caso de uso a activar (p. ej. reportes por WhatsApp + atencion).")
    p.bullet("Relevar cuentas e integraciones disponibles.")
    p.bullet("Puesta en marcha por fases, midiendo resultados en cada una.")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "Propuesta_Agente_IA_Servicios_Megabytes.pdf"
    p.output(str(path))
    return path


if __name__ == "__main__":
    a = build_model_proposal()
    b = build_agent_proposal()
    print("Generado:", a)
    print("Generado:", b)
