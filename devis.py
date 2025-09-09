import io
import csv
import json
import datetime as dt
from dataclasses import dataclass
from typing import List
from pypdf import PdfReader, PdfWriter
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
pdfmetrics.registerFont(TTFont("BodoniF", "bodonif.ttf"))
from reportlab.platypus import Table, TableStyle

# -------------------- Data models --------------------
@dataclass
class StockItem:
    name: str
    color: str
    lot_number: str
    entry_date: str
    quantity: int

@dataclass
class Company:
    name: str
    siret: str = ""
    address: str = ""
    rm: str = ""
    phone: str = ""
    email: str = ""

@dataclass
class Client:
    name: str
    address: str
    phone: str
    email: str
    city: str

@dataclass
class Item:
    description: str
    unit_price: float
    quantity: int

@dataclass
class Quote:
    number: str
    date: dt.date
    client: Client
    items: List[Item]
    discount_value: float
    discount_is_percent: bool
    place: str
    status: str = "quote"  # quote or invoice
    materials: list = None  # [{product, name, lot, qty}]
    serials: list = None     # [{serial, product, materials:[{name, lot, qty}]}]

@dataclass
class RawMaterial:
    name: str = ""
    color: str = ""
    lot_number: str = ""
    entry_date: dt.date = ""
    quantity: int = ""


# -------------------- CSV loaders --------------------
def load_catalog(path="catalog.csv") -> List[Item]:
    try:
        items = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append(Item(row["description"], float(row["unit_price"]), int(row["quantity"])))
        return items
    except FileNotFoundError:
        return []

def load_company(path="company.csv") -> dict:
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
            return {
                "name": row.get("name", ""),
                "siret": row.get("siret", ""),
                "address": row.get("address", ""),
                "rm": row.get("rm", ""),
                "phone": row.get("phone", ""),
                "email": row.get("email", ""),
            }
    except FileNotFoundError:
        return {"name": "", "siret": "", "address": "", "rm": "", "phone": "", "email": ""}
    
def load_clients(path="clients.csv") -> List[Client]:
    try:
        clients = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                clients.append(Client(row["name"], row["address"], row["phone"], str(row["email"]), row["city"]))
        return clients
    except FileNotFoundError:
        return []

def load_quotes(path="quotes.csv") -> List[Quote]:
    try:
        quotes = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Charger les lignes d’articles
                items = [Item(**it) for it in json.loads(row["items"])]

                # Charger client
                client = Client(
                    row["client_name"], row["client_address"],
                    row["client_phone"], row["client_email"], row["client_city"]
                )

                # Charger materials (compatibilité ancienne version)
                try:
                    materials = json.loads(row.get("materials", "[]"))
                except:
                    materials = []

                # Charger serials (nouveau suivi traçabilité)
                try:
                    serials = json.loads(row.get("serials", "[]"))
                except:
                    serials = []

                quotes.append(Quote(
                    number=row["number"],
                    date=dt.datetime.strptime(row["date"], "%Y-%m-%d").date(),
                    client=client,
                    items=items,
                    discount_value=float(row["discount_value"]),
                    discount_is_percent=row["discount_is_percent"] == "True",
                    place=row["place"],
                    status=row.get("status", "quote"),
                    materials=materials,
                    serials=serials
                ))
        return quotes
    except FileNotFoundError:
        return []

    
def load_stock(path="stock.csv") -> List[StockItem]:
    try:
        stock = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stock.append(StockItem(
                    name=row["name"],
                    color=row.get("color", ""),  # <- défaut si pas présent
                    lot_number=row["lot_number"],
                    entry_date=row["entry_date"],
                    quantity=int(row["quantity"])
                ))
        return stock
    except FileNotFoundError:
        return []

# -------------------- CSV savers --------------------
def save_catalog(items: List[Item], path="catalog.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["description", "unit_price", "quantity"])
        writer.writeheader()
        for it in items:
            writer.writerow({"description": it.description, "unit_price": it.unit_price, "quantity": it.quantity})

def save_company(company: dict, path="company.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "siret", "address", "rm", "phone", "email"])
        writer.writeheader()
        writer.writerow(company)

def save_clients(clients: List[Client], path="clients.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "address", "phone", "email", "city"])
        writer.writeheader()
        for cli in clients:
            writer.writerow({"name": cli.name, "address": cli.address, "phone": cli.phone, "email": cli.email, "city": cli.city})

def save_quotes(quotes: List[Quote], path="quotes.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "number","date","client_name","client_address","client_phone","client_email","client_city",
            "items","discount_value","discount_is_percent","place","status","materials","serials"
        ])
        writer.writeheader()
        for q in quotes:
            writer.writerow({
                "number": q.number,
                "date": q.date.isoformat(),
                "client_name": q.client.name,
                "client_address": q.client.address,
                "client_phone": q.client.phone,
                "client_email": q.client.email,
                "client_city": q.client.city,
                "items": json.dumps([vars(it) for it in q.items]),
                "discount_value": q.discount_value,
                "discount_is_percent": q.discount_is_percent,
                "place": q.place,
                "status": q.status,
                "materials": json.dumps(q.materials) if q.materials else "[]",
                "serials": json.dumps(q.serials) if q.serials else "[]"
            })

def save_stock(stock: List[StockItem], path="stock.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "color", "lot_number", "entry_date", "quantity"])
        writer.writeheader()
        for s in stock:
            writer.writerow({
                "name": s.name,
                "color": s.color,
                "lot_number": s.lot_number,
                "entry_date": s.entry_date,
                "quantity": s.quantity
            })


#---------functions------------
def generate_serial(quote_no: str, idx: int) -> str:
    return f"{quote_no}-{idx:03d}"


# -------------------- Load defaults --------------------
DEFAULT_CATALOG = load_catalog()
DEFAULT_COMPANY = load_company()
CLIENTS_DB = load_clients()
QUOTES_DB = load_quotes()
STOCK_DB = load_stock()

# -------------------- Helpers --------------------
def money(v: float) -> str:
    return f"{v:,.2f} €".replace(",", " ").replace(".00", "")

def next_quote_number() -> str:
    today = dt.date.today().strftime("%Y%m%d")
    today_quotes = [q for q in QUOTES_DB if q.number.startswith(today)]
    return f"{today}-{len(today_quotes)+1:03d}"


# -------------------- PDF Builder --------------------

def build_pdf(company: Company, client: Client, items: List[Item], discount_value: float,
              discount_is_percent: bool, quote_no: str, quote_date: dt.date,
              place: str, status="quote", materials: list = None, serials: list = None) -> bytes:
    buf = io.BytesIO()
    width, height = A4
    c = canvas.Canvas(buf, pagesize=A4)

    beige = colors.Color(0.835, 0.914, 0.851)
    black = colors.black
    margin = 18*mm

    # Background header
    c.setFillColor(beige)
    c.rect(0, height-73*mm, width, height-70*mm, fill=1, stroke=0)
    c.setFillColor(black)
    c.rect(0, height-(73*mm)-1, width, 1, fill=1, stroke=0)

    # Title
    c.setFont("BodoniF", 55)
    c.drawCentredString(width/2, height - margin, "Facture" if status=="invoice" else "Devis")

    # Logo
    logo_path = "logo.png"
    logo_width = 30*mm
    logo_height = 20*mm
    try:
        c.drawImage(logo_path, margin/2, height - (margin/2) - logo_height,
                    width=logo_width, height=logo_height, mask='auto')
    except:
        pass

    # Company block
    c.setFont("Helvetica", 10)
    comp_lines = [
        f"Entrepreneur individuel : {company.name}",
        f"SIRET : {company.siret}",
        f"Adresse : {company.address}",
        f"RM : {company.rm}",
        f"Téléphone : {company.phone}",
        f"E-mail : {company.email}",
    ]
    y = height - margin - 15*mm
    for line in comp_lines:
        c.drawString(margin/2, y, line)
        y -= 5*mm

    # Client block
    client_box_top = height - margin - 15*mm
    client_box_left = height/3 + 10*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(client_box_left, client_box_top, "Client")
    c.setFont("Helvetica", 10)
    cli_lines = [
        f"Nom : {client.name}",
        f"Adresse : {client.address}",
        f"Téléphone : {client.phone}",
        f"E-mail : {client.email}",
        f"Fait à : {place}",
        f"Le : {quote_date.strftime('%d/%m/%Y')}",
        f"{('Facture' if status== 'invoice' else 'Devis')} n° : {quote_no}",
    ]
    y2 = client_box_top - 6*mm
    for line in cli_lines:
        c.drawString(client_box_left, y2, line)
        y2 -= 5*mm

    # -------------------------------
    # Tableau des produits + traçabilité
    # -------------------------------

    if status == "invoice" and serials:
        data = [["DESCRIPTION", "PRIX", "N° DE SÉRIE", "TOTAL"]]
    else:
        data = [["DESCRIPTION", "PRIX", "QUANTITE", "TOTAL"]]
    
    
    subtotal = 0.0

    if status == "invoice" and serials:
        for s in serials:
            # Ligne du produit
            line_total = next((it.unit_price for it in items if it.description == s["product"]), 0.0)
            subtotal += line_total
            data.append([
                s["product"],
                money(line_total),
                s["serial"],
                money(line_total)
            ])
            # Lignes indentées des matières premières
            for m in s["materials"]:
                data.append([
                    f"    ↳ {m['name']} (Lot {m['lot']})",
                    "",
                    "",
                    f"{m['qty']} u."
                ])
    else:
        # Cas des devis (quantité affichée normalement)
        for it in items:
            line_total = it.unit_price * it.quantity
            subtotal += line_total
            data.append([it.description, money(it.unit_price), f"{it.quantity:02d}", money(line_total)])

    discount_amount = subtotal * (discount_value / 100.0) if discount_is_percent else min(discount_value, subtotal)
    vat_amount = 0.0
    total = subtotal - discount_amount + vat_amount

    table = Table(data, colWidths=[90*mm, 25*mm, 40*mm, 25*mm])
    style = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), beige),
        ("TEXTCOLOR", (0,0), (-1,0), black),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("ALIGN", (0,0), (0,-1), "LEFT"),
        ("LINEABOVE", (0,0), (-1,0), 1, black),
        ("LINEBELOW", (0,0), (-1,0), 1, black),
        ("LINEBEFORE", (0,0), (-1,0), 1, black),
        ("LINEAFTER", (0,0), (-1,0), 1, black),
    ])
    table.setStyle(style)
    table.wrapOn(c, 0, 0)
    table.drawOn(c, margin, y2-table._height-5)

    # Totaux
    totals_x = margin + 110*mm
    totals_y = y2-table._height-20
    line_h = 6*mm
    c.setFont("Helvetica", 10)
    c.drawRightString(totals_x, totals_y, "Sous total :")
    c.drawRightString(totals_x + 40*mm, totals_y, money(subtotal))
    totals_y -= line_h
    c.drawRightString(totals_x, totals_y, "Remise :")
    c.drawRightString(totals_x + 40*mm, totals_y, ("- " if discount_amount>0 else "") + money(discount_amount))
    totals_y -= line_h
    c.drawRightString(totals_x, totals_y, "TVA (0%) :")
    c.drawRightString(totals_x + 40*mm, totals_y, money(vat_amount))
    totals_y -= line_h
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(totals_x, totals_y, "TOTAL :")
    c.drawRightString(totals_x + 40*mm, totals_y, money(total))

    sig_y = totals_y - 5*mm
    c.setFont("Helvetica-Oblique", 9)
    c.drawRightString(totals_x + 40*mm, sig_y, "TVA non applicable, art. 293 B du CGI")

    # Bloc conditions ou signature
    if status=="invoice":
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin, sig_y - 10*mm, "Condition de paiement :")
        c.setFont("Helvetica", 9)
        c.drawString(margin, sig_y - 16*mm, "Paiement comptant à la réception de la facture. Aucun escompte en cas de paiement anticipé.")
        c.drawString(margin, sig_y - 20*mm, "En cas de retard, pénalités calculées au taux annuel de 10 % .")
    else:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin, sig_y, "Signature du client :")
        c.setFont("Helvetica", 9)
        c.drawString(margin, sig_y - 6*mm, "Je reconnais avoir pris connaissance de ce devis et des conditions de vente inscrites au dos, je les accepte sans réserve.")
        c.drawString(margin, sig_y - 10*mm, 'Signature précédée de la mention "Bon pour accord" :')
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, 5*mm, "Ce devis est valable 30 jours calendaires")

    c.showPage()


    c.save()
    buf.seek(0)
    return(buf.read())


#-------UI----------

st.set_page_config(page_title="Éditeur de Devis", page_icon="📄", layout="wide")
st.title("📄 Éditeur de Devis")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📑 Devis", "🏢 Entreprise", "📦 Catalogue", "👥 Clients", "💶 Factures", "📦 Stock"])

# --- TAB 1: Devis generator ---
with tab1:
    quotes = [q for q in QUOTES_DB if q.status == "quote"]
    if not quotes:
        st.info("Aucun devis enregistré")
    else:
        df_quot = pd.DataFrame([{**vars(quot), "client": quot.client.name, "total": sum(i.unit_price * i.quantity for i in quot.items) - (sum(i.unit_price * i.quantity for i in quot.items) * (quot.discount_value/100 if quot.discount_is_percent else 0))} for quot in quotes])
        st.dataframe(df_quot[["number", "date", "client", "total"]])

    with st.sidebar:
        st.subheader("Informations entreprise")
        comp = Company(
            name=st.text_input("Nom", DEFAULT_COMPANY["name"]),
            siret=st.text_input("SIRET", DEFAULT_COMPANY["siret"]),
            address=st.text_area("Adresse", DEFAULT_COMPANY["address"]),
            rm=st.text_input("RM", DEFAULT_COMPANY["rm"]),
            phone=st.text_input("Téléphone", DEFAULT_COMPANY["phone"]),
            email=st.text_input("E-mail", DEFAULT_COMPANY["email"]),
        )

    st.subheader("Ouvrir un devis existant")
    sel_quote = st.selectbox("Choisir un devis", options=[q.number for q in QUOTES_DB if q.status=="quote"], index=None)
    selected_quote = next((q for q in QUOTES_DB if q.number == sel_quote), None)

    if selected_quote:
        cli = selected_quote.client
        cli.name = st.text_input("Nom du client", value=cli.name)
        cli.address = st.text_input("Adresse du client", value=cli.address)
        cli.phone = st.text_input("Téléphone du client", value=cli.phone)
        cli.email = st.text_input("E-mail du client", value=cli.email)
        cli.city = st.text_input("Ville (lieu de signature)", value=cli.city)

        lines = []
        for i, it in enumerate(selected_quote.items):
            with st.container(border=True):
                desc = st.text_input("Description", value=it.description, key=f"d_{i}")
                qty = st.number_input("Quantité", min_value=1, value=it.quantity, key=f"q_{i}")
                price = st.number_input("Prix unitaire (€)", min_value=0.0, value=it.unit_price, step=1.0, key=f"p_{i}")
                lines.append(Item(desc, price, qty))

        discount_is_percent = st.toggle("Remise en %", value=selected_quote.discount_is_percent)
        discount_value = st.number_input("Valeur de la remise", min_value=0.0, value=selected_quote.discount_value, step=1.0)
        quote_no = selected_quote.number
        quote_date = st.date_input("Date du devis", value=selected_quote.date, format="DD/MM/YYYY")
        place = st.text_input("Fait à", value=selected_quote.place)
    else:
        sel_client = st.selectbox(
            "Sélectionnez un client", options=[client.name for client in CLIENTS_DB], index=None
        )
        selected_client = next((c for c in CLIENTS_DB if c.name == sel_client), None)
        cli = Client(
            name=st.text_input("Nom du client", value=selected_client.name if selected_client else ""),
            address=st.text_input("Adresse du client", value=selected_client.address if selected_client else ""),
            phone=st.text_input("Téléphone du client", value=selected_client.phone if selected_client else ""),
            email=st.text_input("E-mail du client", value=selected_client.email if selected_client else ""),
            city=st.text_input("Ville (lieu de signature)", value=selected_client.city if selected_client else ""),
        )
        sel_names = st.multiselect(
            "Sélectionnez dans le catalogue", options=[it.description for it in DEFAULT_CATALOG],
            default=[it.description for it in DEFAULT_CATALOG[:2]] if DEFAULT_CATALOG else [],
        )
        lines: List[Item] = []
        for name in sel_names:
            base = next((it for it in DEFAULT_CATALOG if it.description == name), None)
            with st.container(border=True):
                desc = st.text_input("Description", value=base.description if base else name, key=f"d_{name}")
                col1, col2 = st.columns(2)
                with col1:
                    qty = st.number_input("Quantité", min_value=1, max_value=999, value=base.quantity if base else 1, key=f"q_{name}")
                with col2:
                    price = st.number_input("Prix unitaire (€)", min_value=0.0, value=base.unit_price if base else 0.0, step=1.0, key=f"p_{name}")
                lines.append(Item(desc, price, qty))
        discount_is_percent = st.toggle("Remise en %", value=True)
        discount_value = st.number_input("Valeur de la remise", min_value=0.0, value=0.0, step=1.0)
        quote_no = next_quote_number()
        quote_date = st.date_input("Date du devis", value=dt.date.today(), format="DD/MM/YYYY")
        place = st.text_input("Fait à", value=cli.city)

    subtotal = sum(it.unit_price * it.quantity for it in lines)
    discount_amount = subtotal * (discount_value / 100.0) if discount_is_percent else min(discount_value, subtotal)
    total = subtotal - discount_amount

    st.metric("Sous-total", money(subtotal))
    st.metric("Remise", ("- " if discount_amount>0 else "") + money(discount_amount))
    st.metric("Total", money(total))

    if st.button("💾 Sauvegarder et Générer PDF"):
        existing = next((q for q in QUOTES_DB if q.number == quote_no), None)
        if existing:
            QUOTES_DB.remove(existing)
        new_quote = Quote(
            number=quote_no,
            date=quote_date,
            client=cli,
            items=lines,
            discount_value=discount_value,
            discount_is_percent=discount_is_percent,
            place=place,
            status="quote"
        )
        QUOTES_DB.append(new_quote)
        save_quotes(QUOTES_DB)

        pdf_bytes = build_pdf(comp, cli, lines, discount_value, discount_is_percent, quote_no, quote_date, place, status="quote")
        st.download_button("Télécharger le devis (PDF)", pdf_bytes, file_name=f"devis_{quote_no}.pdf", mime="application/pdf")

    # Bouton séparé pour transformer en facture
    if selected_quote and st.button("Transformer ce devis en facture"):
        selected_quote.status = "invoice"
        save_quotes(QUOTES_DB)
        st.success(f"Devis {selected_quote.number} transformé en facture ✅")



# --- TAB 2: Company Editor ---
with tab2:
    st.subheader("Modifier les informations de l’entreprise")
    with st.form("company_form"):
        name = st.text_input("Nom", DEFAULT_COMPANY["name"])
        siret = st.text_input("SIRET", DEFAULT_COMPANY["siret"])
        address = st.text_area("Adresse", DEFAULT_COMPANY["address"])
        rm = st.text_input("RM", DEFAULT_COMPANY["rm"])
        phone = st.text_input("Téléphone", DEFAULT_COMPANY["phone"])
        email = st.text_input("E-mail", DEFAULT_COMPANY["email"])
        if st.form_submit_button("💾 Sauvegarder"):
            save_company({"name": name, "siret": siret, "address": address, "rm": rm, "phone": phone, "email": email})
            st.success("Informations entreprise sauvegardées ✅")


# --- TAB 3: Catalog Editor ---
with tab3:
    st.subheader("Modifier le catalogue")
    df = pd.DataFrame([vars(it) for it in DEFAULT_CATALOG])
    edited = st.data_editor(df, num_rows="dynamic", key="editor_catalog")
    if st.button("💾 Sauvegarder le catalogue"):
        items = [Item(row["description"], float(row["unit_price"]), int(row["quantity"])) for _, row in edited.iterrows()]
        save_catalog(items)
        st.success("Catalogue sauvegardé ✅")


# --- TAB 4: Clients Database ---
with tab4:
    st.subheader("Modifier la base clients")
    dc = pd.DataFrame([vars(it) for it in CLIENTS_DB])
    edited_clients = st.data_editor(dc, num_rows="dynamic", key="editor_clients")
    if st.button("💾 Sauvegarder les clients"):
        clients = [Client(row["name"], row["address"], row["phone"], row["email"], row["city"]) for _, row in edited_clients.iterrows()]
        save_clients(clients)
        st.success("Clients sauvegardés ✅")

# --- TAB 5: Factures ---
with tab5:
    st.subheader("Liste des factures")
    invoices = [q for q in QUOTES_DB if q.status == "invoice"]
    if not invoices:
        st.info("Aucune facture enregistrée")
    else:
        df_inv = pd.DataFrame([
            {
                **vars(inv),
                "client": inv.client.name,
                "total": sum(i.unit_price * i.quantity for i in inv.items)
                        - (sum(i.unit_price * i.quantity for i in inv.items)
                           * (inv.discount_value / 100 if inv.discount_is_percent else 0))
            }
            for inv in invoices
        ])
        st.dataframe(df_inv[["number", "date", "client", "total"]])

        sel_invoice = st.selectbox(
            "Choisir une facture à éditer",
            options=[inv.number for inv in invoices],
            index=None,
            key="sel_invoice"
        )
        selected_invoice = next((inv for inv in invoices if inv.number == sel_invoice), None)

        if selected_invoice:
            cli = selected_invoice.client
            lines = selected_invoice.items
            discount_value = selected_invoice.discount_value
            discount_is_percent = selected_invoice.discount_is_percent
            quote_no = selected_invoice.number
            quote_date = selected_invoice.date
            place = selected_invoice.place

            st.write("### Modifier la facture")
            cli.name = st.text_input("Nom du client", value=cli.name, key=f"cli_name_{quote_no}")
            cli.address = st.text_input("Adresse du client", value=cli.address, key=f"cli_addr_{quote_no}")
            cli.phone = st.text_input("Téléphone du client", value=cli.phone, key=f"cli_phone_{quote_no}")
            cli.email = st.text_input("E-mail du client", value=cli.email, key=f"cli_email_{quote_no}")
            cli.city = st.text_input("Ville", value=cli.city, key=f"cli_city_{quote_no}")

            discount_is_percent = st.toggle(
                "Remise en %",
                value=discount_is_percent,
                key=f"inv_toggle_{quote_no}"
            )
            discount_value = st.number_input(
                "Valeur de la remise",
                min_value=0.0,
                value=discount_value,
                step=1.0,
                key=f"inv_discount_{quote_no}"
            )
            place = st.text_input("Fait à", value=place, key=f"inv_place_{quote_no}")

            # -----------------------------
            # Traçabilité par numéros de série
            # -----------------------------
            st.write("### Traçabilité produits (numéros de série)")

            def generate_serial(quote_no: str, idx: int) -> str:
                return f"{quote_no}-{idx:03d}"

            old_serials = getattr(selected_invoice, "serials", []) or []
            new_serials = []
            serial_counter = 1

            for i, it in enumerate(lines):
                for q in range(it.quantity):
                    serial = generate_serial(quote_no, serial_counter)
                    serial_counter += 1

                    st.markdown(f"#### {it.description} — Série {serial}")

                    lot_options = [
                        f"{m.name} - Lot {m.lot_number} ({m.quantity} restants)"
                        for m in STOCK_DB if m.quantity > 0
                    ]

                    # anciens matériaux pour ce numéro de série
                    old_entry = next((s for s in old_serials if s["serial"] == serial), None)
                    preselected = []
                    if old_entry:
                        for mat in old_entry["materials"]:
                            match = next((opt for opt in lot_options if f"Lot {mat['lot']}" in opt), None)
                            if match:
                                preselected.append(match)

                    selected_lots = st.multiselect(
                        f"Lots utilisés pour série {serial}",
                        lot_options,
                        default=preselected,
                        key=f"lots_{quote_no}_{i}_{q}"
                    )

                    materials_for_serial = []
                    for sel in selected_lots:
                        lot_id = sel.split("Lot ")[1].split(" ")[0]
                        material = next((m for m in STOCK_DB if m.lot_number == lot_id), None)
                        if material:
                            old_qty = 1
                            if old_entry:
                                old_qty = next((mat["qty"] for mat in old_entry["materials"] if mat["lot"] == lot_id), 1)
                            qty_used = st.number_input(
                                f"Quantité utilisée de {material.name} (Lot {material.lot_number})",
                                min_value=1,
                                max_value=material.quantity + old_qty,
                                value=old_qty,
                                key=f"qty_{quote_no}_{i}_{q}_{lot_id}"
                            )
                            materials_for_serial.append({
                                "name": material.name,
                                "lot": material.lot_number,
                                "qty": qty_used
                            })

                    new_serials.append({
                        "serial": serial,
                        "product": it.description,
                        "materials": materials_for_serial
                    })

            # Bouton Sauvegarde facture + ajustement stock
            if st.button("💾 Sauvegarder la facture", key=f"save_invoice_{quote_no}"):

                # Ajustement stock par différence
                for ns in new_serials:
                    old_entry = next((s for s in old_serials if s["serial"] == ns["serial"]), None)
                    for mat in ns["materials"]:
                        stock_item = next((m for m in STOCK_DB if m.lot_number == mat["lot"]), None)
                        if stock_item:
                            old_qty = 0
                            if old_entry:
                                old_qty = next((m2["qty"] for m2 in old_entry["materials"] if m2["lot"] == mat["lot"]), 0)
                            diff = mat["qty"] - old_qty
                            stock_item.quantity -= diff

                # Récréditer les lots qui ont disparu
                for old in old_serials:
                    still_present = next((ns for ns in new_serials if ns["serial"] == old["serial"]), None)
                    if still_present:
                        for om in old["materials"]:
                            still_used = any(m["lot"] == om["lot"] for m in still_present["materials"])
                            if not still_used:
                                stock_item = next((m for m in STOCK_DB if m.lot_number == om["lot"]), None)
                                if stock_item:
                                    stock_item.quantity += om["qty"]
                    else:
                        # toute la série a disparu → tout récréditer
                        for om in old["materials"]:
                            stock_item = next((m for m in STOCK_DB if m.lot_number == om["lot"]), None)
                            if stock_item:
                                stock_item.quantity += om["qty"]

                # Mise à jour de la facture
                selected_invoice.client = cli
                selected_invoice.items = lines
                selected_invoice.discount_value = discount_value
                selected_invoice.discount_is_percent = discount_is_percent
                selected_invoice.place = place
                selected_invoice.serials = new_serials

                save_stock(STOCK_DB)
                save_quotes(QUOTES_DB)
                st.success("Facture mise à jour et stock ajusté ✅")

            # Génération PDF avec traçabilité
            pdf_bytes = build_pdf(
                comp, cli, lines,
                discount_value, discount_is_percent,
                quote_no, quote_date, place,
                status="invoice",
                materials=[],
                serials=selected_invoice.serials or []
            )
            st.download_button(
                "Télécharger la facture (PDF)",
                pdf_bytes,
                file_name=f"facture_{quote_no}.pdf",
                mime="application/pdf",
                key=f"dl_invoice_{quote_no}"
            )

# --- TAB 6: stock ---

with tab6:
    st.subheader("Gestion du stock de matières premières")

    df_stock = pd.DataFrame([vars(m) for m in STOCK_DB])
    edited_stock = st.data_editor(df_stock, num_rows="dynamic", key="editor_stock")

    if st.button("💾 Sauvegarder le stock"):
        new_stock = []
        for _, row in edited_stock.iterrows():
            new_stock.append(RawMaterial(
                name=row["name"],
                lot_number=row["lot_number"],
                entry_date=row["entry_date"] if isinstance(row["entry_date"], dt.date) else dt.datetime.strptime(str(row["entry_date"]), "%Y-%m-%d").date(),
                quantity=int(row["quantity"])
            ))
        save_stock(new_stock)
        st.success("Stock sauvegardé ✅")
        STOCK_DB[:] = new_stock
