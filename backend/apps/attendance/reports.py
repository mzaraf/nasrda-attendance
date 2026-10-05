import csv
import io
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import absence
from .models import AttendanceRecord

User = get_user_model()
AGENCY_NAME = "National Space Research and Development Agency"
LOGO_PATH = Path(__file__).resolve().parents[3] / "frontend" / "public" / "logo.png"


def _apply_filters(qs, department=None, campus=None):
    if department:
        qs = qs.filter(user__department_id=department)
    if campus:
        qs = qs.filter(campus_id=campus)
    return qs


def daily_attendance_rows(date, department=None, campus=None):
    qs = _apply_filters(AttendanceRecord.objects.filter(date=date), department, campus) \
        .select_related("user", "user__department", "campus")
    rows = [["IPPIS", "Name", "Department", "Campus", "Check-in", "Check-out", "Status", "Activities"]]
    for r in qs:
        rows.append([r.user.ippis_number, r.user.get_full_name(),
                    r.user.department.name if r.user.department_id else "", r.campus.name,
                    timezone.localtime(r.check_in_at).strftime("%H:%M"),
                    timezone.localtime(r.check_out_at).strftime("%H:%M") if r.check_out_at else "—",
                    r.check_in_status, r.activities.count()])
    return rows, f"Daily Attendance Report — {date}"


def monthly_summary_rows(year, month, department=None, campus=None):
    # Monthly attendance includes everyone in the selected scope, including staff who
    # never checked in. Otherwise their absence would be invisible in the report.
    staff = User.objects.filter(is_active=True).select_related("department")
    if department:
        staff = staff.filter(department_id=department)
    if campus:
        staff = staff.filter(primary_campus_id=campus)
    staff_by_id = {user.id: user for user in staff}

    first_day = date(year, month, 1)
    working_dates = []
    for offset in range(monthrange(year, month)[1]):
        current = first_day + timedelta(days=offset)
        if absence.is_working_day(current):
            working_dates.append(current)

    qs = AttendanceRecord.objects.filter(user_id__in=staff_by_id, date__year=year, date__month=month)
    by_user = {user_id: {"user": user, "present_dates": set()} for user_id, user in staff_by_id.items()}
    for r in qs:
        by_user[r.user_id]["present_dates"].add(r.date)

    leave_by_date = {day: absence.on_approved_leave(day) for day in working_dates}
    duty_by_date = {day: absence.on_official_duty(day) for day in working_dates}
    rows = [["IPPIS", "Name", "Department", "Days present", "Days absent", "Attendance percentage"]]
    for b in by_user.values():
        u = b["user"]
        present = len(b["present_dates"] & set(working_dates))
        excused = sum(u.id in (leave_by_date[day] | duty_by_date[day]) and day not in b["present_dates"] for day in working_dates)
        eligible_days = max(len(working_dates) - excused, 0)
        absent = max(eligible_days - present, 0)
        percentage = f"{(present / eligible_days * 100):.1f}%" if eligible_days else "—"
        rows.append([u.ippis_number, u.get_full_name(), u.department.name if u.department_id else "",
                    present, absent, percentage])
    return rows, f"Monthly Attendance Summary — {year}-{month:02d}"


REPORT_BUILDERS = {"daily": daily_attendance_rows}


def to_csv(rows):
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def to_xlsx(rows, title):
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    ws.sheet_view.showGridLines = False
    columns = max(len(rows[0]), 1)
    if LOGO_PATH.exists():
        logo = ExcelImage(str(LOGO_PATH))
        logo.width = logo.height = 58
        ws.add_image(logo, "A1")
    ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=columns)
    ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=columns)
    ws.cell(1, 2, AGENCY_NAME)
    ws.cell(2, 2, title)
    ws.cell(1, 2).font = Font(name="Aptos Display", size=15, bold=True, color="19297D")
    ws.cell(2, 2).font = Font(name="Aptos", size=11, bold=True, color="31435B")
    ws.cell(1, 2).alignment = ws.cell(2, 2).alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height, ws.row_dimensions[2].height = 32, 24
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=columns)
    ws.cell(3, 1, f"Generated on {timezone.localtime().strftime('%d %b %Y, %H:%M')} (Africa/Lagos)")
    ws.cell(3, 1).font = Font(italic=True, color="667085", size=10)
    ws.cell(3, 1).alignment = Alignment(horizontal="left")
    for row_index, row in enumerate(rows, start=5):
        for column_index, value in enumerate(row, start=1):
            cell = ws.cell(row_index, column_index, value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if row_index == 5:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="19297D")
                cell.alignment = Alignment(vertical="center", wrap_text=True)
            elif row_index % 2 == 1:
                cell.fill = PatternFill("solid", fgColor="F4F7FB")
            cell.border = Border(bottom=Side(style="hair", color="D5DDE8"))
    for column_index, header in enumerate(rows[0], start=1):
        width = max(len(str(header)) + 4, *(len(str(row[column_index - 1])) + 2 for row in rows[1:]))
        ws.column_dimensions[chr(64 + column_index)].width = min(max(width, 12), 32)
    ws.freeze_panes = "A6"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_pdf(rows, title, generated_by):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=14 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    agency_style = ParagraphStyle("Agency", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=16,
                                  leading=19, textColor=colors.HexColor("#19297D"), spaceAfter=2, alignment=0)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=8.5, leading=11,
                                    textColor=colors.HexColor("#667085"), spaceAfter=12)
    report_style = ParagraphStyle("ReportTitle", parent=styles["Heading2"], fontSize=12, leading=15,
                                  textColor=colors.HexColor("#14212E"), spaceAfter=4)
    meta_style = ParagraphStyle("Metadata", parent=styles["Normal"], fontSize=8.5, leading=11,
                                textColor=colors.HexColor("#52657B"), spaceAfter=10)
    when = timezone.localtime().strftime("%d %b %Y %H:%M")
    # A nested table keeps the agency name and subtitle in the same right-hand
    # header column; passing a raw list of flowables lets ReportLab lay the
    # subtitle out as an independent row starting at the page margin.
    brand_block = Table([
        [Paragraph(AGENCY_NAME, agency_style)],
        [Paragraph("Staff Attendance Management System", subtitle_style)],
    ], colWidths=[158 * mm])
    brand_block.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                     ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    header = [[Image(str(LOGO_PATH), width=19 * mm, height=19 * mm) if LOGO_PATH.exists() else "", brand_block]]
    header_table = Table(header, colWidths=[24 * mm, 158 * mm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                      ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                      ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    usable_width = A4[0] - doc.leftMargin - doc.rightMargin
    # Allocate width by the longest value in each column and render every cell as a
    # paragraph, so names and long headings never run outside their cells.
    column_weights = [min(max(max(len(str(row[index])) for row in rows), 9), 28) for index in range(len(rows[0]))]
    total_weight = sum(column_weights)
    widths = [usable_width * weight / total_weight for weight in column_weights]
    header_cell_style = ParagraphStyle("TableHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5,
                                       leading=9, textColor=colors.white)
    body_cell_style = ParagraphStyle("TableBody", parent=styles["Normal"], fontSize=7.5, leading=9, textColor=colors.HexColor("#14212E"))
    pdf_rows = [[Paragraph(str(value), header_cell_style if row_index == 0 else body_cell_style)
                 for value in row] for row_index, row in enumerate(rows)]
    table = Table(pdf_rows, repeatRows=1, colWidths=widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#19297D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CDD7E4")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FB")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D5DDE8"))
        canvas.line(document.leftMargin, 10 * mm, A4[0] - document.rightMargin, 10 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(document.leftMargin, 6 * mm, AGENCY_NAME)
        canvas.drawRightString(A4[0] - document.rightMargin, 6 * mm, f"Page {document.page}")
        canvas.restoreState()
    doc.build([header_table, Spacer(1, 8), Paragraph(title, report_style),
               Paragraph(f"Generated by {generated_by} on {when} (Africa/Lagos)", meta_style), table],
              onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
