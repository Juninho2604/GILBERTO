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

    def _ensure(self, h: float):
        """Salta de pagina si no entra un bloque de alto ``h``."""
        if self.get_y() + h > self.h - self.b_margin:
            self.add_page()

    def section(self, title: str):
        self._ensure(16)
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
            self.multi_cell(0, 5.6, s(text), align="L")
        else:
            self.set_font("Helvetica", "", 10.5)
            self.set_text_color(*INK)
            self.multi_cell(0, 5.6, s(text), align="L")
        self.ln(0.6)

    def price_row(self, concept: str, amount: str, note: str = "", highlight=False):
        self._ensure(24 if note else 11)
        if highlight:
            self.set_fill_color(*ACCENT)
            self.rect(18, self.get_y() + 1, 1.6, 6, "F")  # barra de acento (no se rompe)
        self.set_x(22 if highlight else 18)
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B" if highlight else "", 10.5)
        self.cell(126 if highlight else 130, 8, s(concept))
        self.set_text_color(*(ACCENT if highlight else INK))
        self.set_font("Helvetica", "B", 11.5)
        self.cell(44, 8, s(amount), align="R", ln=1)
        if note:
            self.set_x(22 if highlight else 18)
            self.set_text_color(*MUTED)
            self.set_font("Helvetica", "", 8.7)
            self.multi_cell(170, 4.6, s(note), align="L")
        self.set_draw_color(232, 236, 242)
        self.line(18, self.get_y() + 1.5, 192, self.get_y() + 1.5)
        self.ln(3.5)

    def callout(self, text: str):
        self.set_font("Helvetica", "", 10)
        # estimacion de alto para no cortar el bloque entre paginas
        approx_lines = max(2, int(self.get_string_width(s(text)) / 160) + 1)
        self._ensure(approx_lines * 5.4 + 8)
        x0, y0 = 18, self.get_y()
        self.set_xy(x0 + 5, y0 + 3)
        self.set_text_color(*INK)
        self.multi_cell(164, 5.4, s(text))
        y1 = self.get_y()
        self.set_fill_color(*ACCENT)
        self.rect(x0, y0, 1.6, y1 - y0 + 3, "F")  # barra de acento
        self.ln(4)


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
    p.price_row("Construccion e implementacion", "$2.500", "Pago unico. Despliegue en el servidor, carga de datos reales, validacion y capacitacion del operario que arma los lotes.", highlight=True)
    p.price_row("Mensualidad", "$300 / mes", "Hosting, soporte, actualizaciones y mejoras del modelo.")
    p.price_row("Piloto (meses 1 y 2)", "Sin fee", "Modo acompanamiento: el sistema guia el armado de lotes y se mide prediccion vs. liquidacion real. Sin fee de exito.")
    p.price_row("Fee de exito (desde mes 3)", "5%", "Unicamente sobre el METAL SUB-UMBRAL rescatado y confirmado por la liquidacion de la refineria. Con tope mensual.", highlight=True)
    p.callout(
        "El costo fijo es una fraccion minima del volumen anual que pasa por la "
        "refineria. El fee de exito es deliberadamente acotado: solo se cobra "
        "cuando el sistema rescata, de forma comprobable, metal que de otro modo "
        "habria pagado $0."
    )

    p.section("5. Como se mide el fee (material sub-umbral)")
    p.para(
        "La refineria descuenta una deduccion por tonelada (p. ej. 100 g/t de "
        "plata, 18 g/t de paladio) antes de pagar. Una pila por debajo de ese "
        "umbral paga $0. Mezclada segun el sistema, el lote supera el umbral y ese "
        "metal se cobra. Ese metal rescatado es 100% atribuible al modelo y es lo "
        "unico sobre lo que se cobra el fee."
    )
    p.bullet("el operario arma el lote en el sistema (como ya esta planeado); la liquidacion llega igual. No hay tarea adicional para Gilberto ni su gente.", "Cero doble trabajo:")
    p.bullet("el fee se calcula solo sobre lo que la liquidacion de la refineria confirma como pagado.", "Confirmado por la refineria:")
    p.bullet("reconciliacion mensual firmada por ambas partes, con tope.", "Transparente:")

    p.section("6. Por que se puede confiar")
    p.bullet("reproduce el pago real de la refineria con +/-3%, validado sobre 53 lotes historicos.", "Validado:")
    p.bullet("el sistema propone y explica; Gilberto y su operario aprueban cada lote. Nunca se envia algo que no se entienda.", "Humano al mando:")
    p.bullet("alertas antes de enviar: metal sub-umbral, lote sobre-diluido, leyes de baja confianza.", "Guardrails:")
    p.bullet("las pilas ricas se confirman con ensayo de laboratorio antes de un envio grande.", "Sin apuestas:")

    p.section("7. Proximos pasos")
    p.bullet("Desplegar el sistema y cargar el inventario y los terminos reales.")
    p.bullet("Piloto de 2 meses midiendo prediccion vs. liquidacion, sin fee.")
    p.bullet("Desde el mes 3, fee del 5% sobre el metal sub-umbral rescatado y confirmado.")

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
