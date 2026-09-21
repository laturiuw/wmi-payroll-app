from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import mm
from datetime import datetime

def format_currency(value):
    if value == 0 or value == 0.0 or not value:
        return "0"
    try:
        return "{:,.0f}".format(float(value))
    except:
        return str(value)

def create_payroll_pdf(filename, report_type, period_name, dataframe, emp_details_dict):
    # A4 Size with 5mm margins on sides and bottom, 25mm on top
    doc = SimpleDocTemplate(filename, pagesize=landscape(A4), rightMargin=5*mm, leftMargin=5*mm, topMargin=25*mm, bottomMargin=5*mm)
    elements = []
    
    styles = getSampleStyleSheet()
    
    r_indent = 100 if report_type == 'NETT' else 0
    
    title_style = ParagraphStyle(name='TitleStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, alignment=TA_CENTER, spaceAfter=5, rightIndent=r_indent)
    sub_style = ParagraphStyle(name='SubStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=12, alignment=TA_CENTER, spaceAfter=5, rightIndent=r_indent)
    date_style = ParagraphStyle(name='DateStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, alignment=TA_LEFT, spaceAfter=5)
    
    elements.append(Paragraph("PT. WOW MULTINET INVESTINDO", title_style))
    elements.append(Paragraph(f"PAYROLL REPORT - {report_type}", sub_style))
    elements.append(Paragraph(period_name, sub_style))
    elements.append(Spacer(1, 15))
    
    today_str = datetime.now().strftime("%d - %b - %Y")
    elements.append(Paragraph(f"D A T E : &nbsp;&nbsp;&nbsp; {today_str}", date_style))
    elements.append(Spacer(1, 5)) 
    
    if report_type == 'GROSS':
        headers = ['No', "Emp'e No", 'Employee Name', 'Title', 'CC', 'Department', 'Join Date', 
                   'Basic\nSalary', 'Work\nDays', 'THR\nMonths', 'Base\nPay', 'Functional\nAllowance', 
                   'Selling\nCommision', 'Tranport\nAllowance', 'Other\nAllowance', 'BPJS-Naker\nDeath & Disab', 
                   'BPJS-Kes\nKesehatan', 'Sub\nGross', 'Tax\nAllowance', 'Bonus', 'THR', 'Other /\nAdjustment', 'Total\nGross']
    else:
        headers = ['No', "Emp'e No", 'Employee Name', 'Title', 'CC', 'Department', 'Join Date', 
                   'Total\nGross', 'Income Tax\nPPh - 21', 'Loan / Advance\nInstallment', 'Travel\nAdvance', 
                   'Deduction\nOther', 'BPJS-Naker\nDeath', 'BPJS-Kes\nKesehatan', 'BPJS-Naker\nJHT', 
                   'BPJS-Naker\nPension', 'Amount\nPaid', 'Net\nSalary', "BPJS-Naker\nJHT+PensCo's", 'Total Gross\nCompany Paid']

    dummy_row = ['' for _ in headers]
    data = [dummy_row, headers]
    totals = {h: 0 for h in headers[7:]}
    
    for i, row in dataframe.iterrows():
        emp_id = row['employee_id']
        emp = emp_details_dict.get(emp_id, {})
        join_date_fmt = emp.get('join_date', '')
        if join_date_fmt:
            try:
                join_date_fmt = datetime.strptime(join_date_fmt, "%Y-%m-%d").strftime("%d-%b-%y")
            except:
                pass
                
        # Shorten titles
        raw_title = str(emp.get('employee_title', ''))
        if 'Executive' in raw_title: emp_title = 'CEO'
        elif 'Financial' in raw_title: emp_title = 'CFO'
        else: emp_title = raw_title
                
        row_data = [
            str(i + 1),
            str(emp_id),
            str(row['employee_name']),
            emp_title,
            str(emp.get('cost_center', '')),
            str(emp.get('department', '')),
            str(join_date_fmt)
        ]
        
        if report_type == 'GROSS':
            numeric_vals = [
                row.get('basic_salary', 0), row.get('work_days', 0), row.get('thr_months', 0), row.get('base_pay', 0),
                row.get('functional_allowance', 0), row.get('selling_commission', 0), row.get('transport_allowance', 0),
                row.get('other_allowance_jht', 0), row.get('bpjs_naker_allowance', 0), row.get('bpjs_kes_allowance', 0),
                row.get('sub_gross', 0), row.get('tax_allowance', 0), row.get('bonus', 0), row.get('thr', 0),
                row.get('other_adjustment', 0), row.get('total_gross', 0)
            ]
        else:
            numeric_vals = [
                row.get('total_gross', 0),
                row.get('tax_allowance', 0) * -1 if row.get('tax_allowance', 0) != 0 else 0,
                row.get('loan_installment', 0),
                row.get('travel_advance', 0),
                row.get('other_deduction', 0),
                row.get('bpjs_naker_allowance', 0) * -1 if row.get('bpjs_naker_allowance', 0) != 0 else 0,
                row.get('bpjs_kes_allowance', 0) * -1 if row.get('bpjs_kes_allowance', 0) != 0 else 0,
                row.get('other_allowance_jht', 0) * -1 if row.get('other_allowance_jht', 0) != 0 else 0,
                row.get('bpjs_naker_pension_deduction', 0),
                row.get('amount_paid', 0),
                row.get('net_salary', 0),
                row.get('basic_salary', 0) * 0.037, 
                row.get('total_gross', 0) + (row.get('basic_salary', 0) * 0.037)
            ]
            
        for idx, val in enumerate(numeric_vals):
            totals[headers[7 + idx]] += float(val)
            if headers[7 + idx] in ['Work\nDays', 'THR\nMonths']:
                row_data.append(str(int(val)))
            elif report_type == 'NETT' and val < 0:
                row_data.append(f"({format_currency(abs(val))})")
            else:
                row_data.append(format_currency(val))
                
        data.append(row_data)
        
    total_row = ['' for _ in headers]
    total_row[2] = 'TOTAL'
    for idx, h in enumerate(headers[7:]):
        val = totals[h]
        if h in ['Work\nDays', 'THR\nMonths']:
            total_row[7 + idx] = str(int(val))
        elif report_type == 'NETT' and val < 0:
            total_row[7 + idx] = f"({format_currency(abs(val))})"
        else:
            total_row[7 + idx] = format_currency(val)
            
    data.append(total_row)
    
    row_heights = [1, 45] + [30] * (len(data) - 3) + [37]
    
    # Define exact column widths to force fit into A4
    if report_type == 'GROSS':
        col_widths = [15, 40, 60, 20, 20, 50, 35, 40, 20, 22, 40, 35, 35, 35, 35, 40, 40, 45, 35, 30, 25, 35, 45]
    else:
        col_widths = [15, 40, 60, 20, 20, 50, 35, 45, 40, 35, 35, 35, 35, 40, 35, 35, 35, 45, 45, 50]
        
    t = Table(data, repeatRows=2, hAlign='LEFT', rowHeights=row_heights, colWidths=col_widths)
    
    style = TableStyle([
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 5.5),
        ('ALIGN', (0,1), (-1,1), 'CENTER'),            
        ('ALIGN', (0,2), (6,-1), 'LEFT'),              
        ('ALIGN', (7,2), (-1,-1), 'RIGHT'),            
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),
        
        ('LEFTPADDING', (0,0), (0,-1), 4),
        
        ('LINEBELOW', (0,0), (-1,0), 1.0, colors.black),   
        ('LINEBELOW', (0,1), (-1,1), 1.0, colors.black),   
        ('LINEBELOW', (0,2), (-1,-2), 0.25, colors.lightgrey), 
        ('LINEABOVE', (0,-1), (-1,-1), 1.0, colors.black), 
        ('LINEBELOW', (0,-1), (-1,-1), 1.0, colors.black), 
        
        ('LINEBEFORE', (0,0), (0,-1), 1.0, colors.black),
        ('LINEAFTER', (-1,0), (-1,-1), 1.0, colors.black),
    ])
    t.setStyle(style)
    elements.append(t)
    
    elements.append(Spacer(1, 30))
    sig_data = [['', 'Prepared by', '', 'Approved by'], ['', '\n\n\nArthur Laturiuw', '', '\n\n\nSteven Sugianto']]
    sig_t = Table(sig_data, colWidths=[30, 200, 400, 200], hAlign='LEFT')
    sig_style = TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ])
    sig_t.setStyle(sig_style)
    elements.append(sig_t)
    
    doc.build(elements)
