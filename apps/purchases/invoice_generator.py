import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from apps.company_settings.models import CompanySettings

def generate_invoice_pdf(payment) -> bytes:
    """
    Generates a clean PDF invoice using ReportLab and returns raw PDF bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    story = []
    styles = getSampleStyleSheet()

    # Load Company Settings
    company_name = "AssetTrak System"
    company_address = "Operations Headquarters"
    company_phone = ""
    company_email = ""
    try:
        settings = CompanySettings.objects.first()
        if settings:
            if settings.company_name:
                company_name = settings.company_name
            if settings.company_address:
                company_address = settings.company_address.replace('\n', ', ')
            if settings.company_phone:
                company_phone = f"Phone: {settings.company_phone}"
            if settings.official_email:
                company_email = f"Email: {settings.official_email}"
    except Exception:
        pass

    # Colors
    primary_color = colors.HexColor("#091426")
    secondary_color = colors.HexColor("#1e293b")
    light_bg = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#e2e8f0")

    # Typography / Styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=primary_color,
        spaceAfter=15
    )
    meta_style = ParagraphStyle(
        'InvoiceMeta',
        fontSize=10,
        textColor=colors.HexColor("#475569"),
        leading=14
    )
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=primary_color,
        spaceBefore=15,
        spaceAfter=8
    )
    body_style = ParagraphStyle(
        'InvoiceBody',
        parent=styles['Normal'],
        fontSize=9,
        leading=14
    )
    bold_style = ParagraphStyle(
        'InvoiceBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    # Document Header Table (Company vs Invoice Meta)
    header_data = [
        [
            Paragraph(f"<b>{company_name}</b><br/>{company_address}<br/>{company_phone}<br/>{company_email}", meta_style),
            Paragraph(f"<b>INVOICE</b><br/><br/>Invoice No: <b>{payment.invoice_number or 'N/A'}</b><br/>Date: {payment.payment_date}<br/>PO Reference: {payment.purchase.purchase_number if payment.purchase else 'N/A'}", meta_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 230])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))

    # Supplier vs Asset Details
    supplier = payment.purchase.supplier if payment.purchase else None
    asset = payment.purchase.asset if payment.purchase else None
    category_name = asset.category.name if (asset and asset.category) else 'N/A'
    asset_name = asset.name if asset else 'N/A'
    purchase_price = payment.purchase.purchase_price if payment.purchase else 'N/A'
    quantity = payment.purchase.quantity if payment.purchase else 'N/A'
    total_amount = payment.purchase.total_amount if payment.purchase else 'N/A'

    supplier_details = f"<b>{supplier.company if supplier else 'N/A'}</b>"
    if supplier and supplier.name:
        supplier_details += f"<br/>Contact: {supplier.name}"
    if supplier and supplier.email:
        supplier_details += f"<br/>Email: {supplier.email}"
    if supplier and supplier.phone:
        supplier_details += f"<br/>Phone: {supplier.phone}"

    details_data = [
        [
            Paragraph("<b>Vendor / Supplier</b>", heading_style),
            Paragraph("<b>Purchased Asset</b>", heading_style)
        ],
        [
            Paragraph(supplier_details, body_style),
            Paragraph(f"<b>{asset_name}</b><br/>Category: {category_name}<br/>Unit Price: {purchase_price}<br/>Quantity Ordered: {quantity}", body_style)
        ]
    ]
    details_table = Table(details_data, colWidths=[265, 265])
    details_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 15))

    # Transaction Table
    story.append(Paragraph("<b>Payment Installment Summary</b>", heading_style))
    tx_data = [
        [Paragraph("<b>Item Description</b>", bold_style), Paragraph("<b>Details</b>", bold_style)],
        [Paragraph("Purchase Order Total Amount", body_style), Paragraph(f"{total_amount}", body_style)],
        [Paragraph(f"Payment Installment ({payment.method})", bold_style), Paragraph(f"<b>{payment.amount}</b>", bold_style)],
        [Paragraph("Transaction Reference / ID", body_style), Paragraph(f"{payment.reference or 'N/A'}", body_style)],
    ]
    tx_table = Table(tx_data, colWidths=[350, 180])
    tx_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('BACKGROUND', (0,2), (-1,2), light_bg),
    ]))
    # Quick fix for text color in table headers - override style
    for i in range(2):
        tx_data[0][i].style.textColor = colors.white
    story.append(tx_table)

    story.append(Spacer(1, 40))
    story.append(Paragraph("Thank you for your business!", ParagraphStyle('Footer', parent=styles['Normal'], alignment=1, fontSize=10, textColor=colors.HexColor("#64748b"))))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
