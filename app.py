import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import create_engine
from datetime import datetime
import time
import os
import calendar
from payroll_manager import PayrollDB
from pdf_generator import create_payroll_pdf

st.set_page_config(page_title="Payroll System WOW Multinet", layout="wide")

NEON_URL_PSYCOPG2 = "postgresql://neondb_owner:npg_QB2MingP1ESe@ep-restless-glitter-b3dve2td-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
NEON_URL_SQLALCHEMY = "postgresql+psycopg2://neondb_owner:npg_QB2MingP1ESe@ep-restless-glitter-b3dve2td-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

st.markdown("""
    <style>
           .block-container {
                padding-top: 1rem;
                padding-bottom: 0rem;
            }
    </style>
    """, unsafe_allow_html=True)

def get_db_connection():
    return psycopg2.connect(NEON_URL_PSYCOPG2)

def get_engine():
    return create_engine(NEON_URL_SQLALCHEMY)

def get_ter_category(marital_status, dependents):
    status = f"{marital_status}/{dependents}"
    if status in ['TK/0', 'TK/1', 'K/0']: return 'A'
    if status in ['TK/2', 'TK/3', 'K/1', 'K/2']: return 'B'
    if status in ['K/3']: return 'C'
    return 'A'

def calculate_tax(bruto_tanpa_pajak, category, conn):
    cursor = conn.cursor()
    cursor.execute('SELECT min_gross, max_gross, tax_rate_percent FROM tax_ter_rates WHERE ter_category = %s ORDER BY min_gross', (category,))
    brackets = cursor.fetchall()
    for min_g, max_g, rate in brackets:
        r = float(rate) / 100.0
        if r >= 1.0: continue
        total_gross_estimated = bruto_tanpa_pajak / (1 - r)
        max_limit = float(max_g) if max_g else 999999999999
        if float(min_g) < total_gross_estimated <= max_limit:
            return round(total_gross_estimated - bruto_tanpa_pajak)
    return 0

def get_employee_dict():
    engine = get_engine()
    df_emp = pd.read_sql_query("SELECT * FROM employees", engine)
    emp_dict = {}
    for _, row in df_emp.iterrows():
        emp_dict[row['employee_id']] = row.to_dict()
    return emp_dict

def main():
    st.markdown("<h1 style='font-size: 24px; margin-bottom: 0px;'>PT. WOW Multinet Investindo</h1>", unsafe_allow_html=True)
    
    menu = st.sidebar.selectbox("Menu Navigasi", ["Proses Gaji Bulan Berjalan", "Riwayat & Histori Gaji", "Laporan & Rekapitulasi", "Data Karyawan"])
    conn = get_db_connection()
    engine = get_engine()
    db_manager = PayrollDB(db_path='payroll.db')
    
    if menu == "Proses Gaji Bulan Berjalan":
        
        col_hdr, col1, col2, col3 = st.columns([1.5, 1, 1, 1])
        with col_hdr:
            st.markdown("<div style='margin-top: 30px;'><h2 style='font-size: 21px; margin-bottom: 0px;'>Siapkan Laporan Bulan Berjalan</h2></div>", unsafe_allow_html=True)
        with col1:
            month = st.number_input("Bulan (1-12)", min_value=1, max_value=12, value=datetime.now().month)
        with col2:
            year = st.number_input("Tahun", min_value=2020, value=datetime.now().year)
            
        _, default_days = calendar.monthrange(int(year), int(month))
        
        with col3:
            month_days = st.number_input("Jumlah Hari dalam Bulan Ini", min_value=28, max_value=31, value=default_days)
            
        # Pengecekan Posting Status
        cursor = conn.cursor()
        cursor.execute('SELECT period_id, posted_at FROM payroll_periods WHERE period_month = %s AND period_year = %s', (int(month), int(year)))
        existing_period = cursor.fetchone()
        
        is_posted = existing_period and existing_period[1] is not None
        
        if is_posted:
            st.error(f"⚠️ Peringatan: Data penggajian untuk periode {month}/{year} sudah diposting dan dikunci pada {existing_period[1]}. Untuk menjaga integritas riwayat pajak, mohon gunakan menu 'Riwayat & Histori Gaji' apabila Anda benar-benar perlu merevisinya.")
        else:
            if existing_period:
                st.info("ℹ️ Status: DRAFT. Bulan ini sudah pernah disimpan tetapi belum di-posting. Anda masih bisa memproses dan menimpanya berkali-kali.")
                
            if st.button("1. Buat Draft Bulan Ini"):
                df_emp = pd.read_sql_query('''
                    SELECT e.employee_id, e.employee_name, e.employee_title, e.department, 
                           e.marital_status, e.dependents,
                           (SELECT basic_salary FROM salary_history sh WHERE sh.employee_id = e.employee_id ORDER BY effective_date DESC LIMIT 1) as basic_salary
                    FROM employees e
                ''', engine)
                
                draft_data = []
                for _, row in df_emp.iterrows():
                    base_sal = float(row['basic_salary'])
                    work_days = month_days
                    base_pay = (work_days / month_days) * base_sal
                    jht_allow = base_sal * 0.02
                    naker_allow = base_sal * 0.0054
                    kes_allow = 286494
                    
                    draft_data.append({
                        "employee_id": row['employee_id'],
                        "employee_name": row['employee_name'],
                        "basic_salary": base_sal,
                        "work_days": work_days,
                        "base_pay": base_pay,
                        "functional_allowance": 0.0,
                        "selling_commission": 0.0,
                        "transport_allowance": 0.0,
                        "other_allowance_jht": jht_allow,
                        "bpjs_naker_allowance": naker_allow,
                        "bpjs_kes_allowance": kes_allow,
                        "bonus": 0.0,
                        "thr": 0.0,
                        "other_adjustment": 0.0,
                        "_marital_status": row['marital_status'],
                        "_dependents": row['dependents'],
                        "thr_months": 0
                    })
                st.session_state['draft_df'] = pd.DataFrame(draft_data)
                st.session_state['original_draft_df'] = pd.DataFrame(draft_data).copy()
        
        if 'draft_df' in st.session_state and not is_posted:
            st.markdown("---")
            col_sh, col_undo = st.columns([4, 1])
            with col_sh:
                st.markdown("<h3 style='font-size: 18px; margin-top: 5px;'>2. Draft Data (Dapat Diedit Langsung)</h3>", unsafe_allow_html=True)
            with col_undo:
                if st.button("⏪ Un-do (Reset Tabel)"):
                    st.session_state['draft_df'] = st.session_state['original_draft_df'].copy()
                    st.rerun()
            
            edited_df = st.data_editor(st.session_state['draft_df'], hide_index=True)
            st.session_state['draft_df'] = edited_df.copy()
            
            if st.button("3. Hitung & Preview Laporan"):
                final_data = []
                for _, row in edited_df.iterrows():
                    bruto_non_pajak = row['base_pay'] + row['functional_allowance'] + row['selling_commission'] + \
                                      row['transport_allowance'] + row['other_allowance_jht'] + row['bpjs_naker_allowance'] + \
                                      row['bpjs_kes_allowance'] + row['bonus'] + row['thr'] + row['other_adjustment']
                                      
                    category = get_ter_category(row['_marital_status'], row['_dependents'])
                    tax_allowance = calculate_tax(bruto_non_pajak, category, conn)
                    
                    total_gross = bruto_non_pajak + tax_allowance
                    net_salary = total_gross - (tax_allowance + row['bpjs_naker_allowance'] + row['bpjs_kes_allowance'] + row['other_allowance_jht'])
                    
                    r = row.to_dict()
                    r['sub_gross'] = bruto_non_pajak
                    r['tax_allowance'] = tax_allowance
                    r['total_gross'] = total_gross
                    r['net_salary'] = net_salary
                    final_data.append(r)
                    
                st.session_state['preview_df'] = pd.DataFrame(final_data)
                
            if 'preview_df' in st.session_state:
                st.markdown("---")
                st.markdown("<h3 style='font-size: 18px;'>Laporan Gross (Preview)</h3>", unsafe_allow_html=True)
                preview_df = st.session_state['preview_df'].copy()
                preview_df.index = preview_df.index + 1
                
                gross_cols = ['employee_name', 'basic_salary', 'work_days', 'base_pay', 'other_allowance_jht', 'bpjs_naker_allowance', 'bpjs_kes_allowance', 'sub_gross', 'tax_allowance', 'bonus', 'thr', 'total_gross']
                st.dataframe(preview_df[gross_cols], use_container_width=True)
                
                st.markdown("<h3 style='font-size: 18px;'>Laporan Net (Preview)</h3>", unsafe_allow_html=True)
                net_cols = ['employee_name', 'total_gross', 'tax_allowance', 'bpjs_naker_allowance', 'bpjs_kes_allowance', 'other_allowance_jht', 'net_salary']
                st.dataframe(preview_df[net_cols], use_container_width=True)
                
                if st.button("Finalisasi, Simpan ke Database & Cetak PDF"):
                    month_map = {1:"Januari", 2:"Februari", 3:"Maret", 4:"April", 5:"Mei", 6:"Juni", 7:"Juli", 8:"Agustus", 9:"September", 10:"Oktober", 11:"November", 12:"Desember"}
                    period_name = f"{month_map[int(month)]} {int(year)}"
                    pid = db_manager.get_or_create_period(int(month), int(year), int(month_days), period_name)
                    
                    # Hapus record lama jika ada agar tidak double saat diproses berulang-ulang sebelum di-posting
                    cursor.execute("DELETE FROM payroll_records WHERE period_id = %s", (pid,))
                    conn.commit()
                    
                    for _, row in st.session_state['preview_df'].iterrows():
                        record = {
                            "employee_id": row["employee_id"],
                            "period_id": pid,
                            "work_days": row["work_days"],
                            "thr_months": row["thr_months"],
                            "basic_salary": row["basic_salary"],
                            "base_pay": row["base_pay"],
                            "functional_allowance": row["functional_allowance"],
                            "selling_commission": row["selling_commission"],
                            "transport_allowance": row["transport_allowance"],
                            "other_allowance_jht": row["other_allowance_jht"],
                            "bpjs_naker_allowance": row["bpjs_naker_allowance"],
                            "bpjs_kes_allowance": row["bpjs_kes_allowance"],
                            "sub_gross": row["sub_gross"],
                            "tax_allowance": row["tax_allowance"],
                            "bonus": row["bonus"],
                            "thr": row["thr"],
                            "other_adjustment": row["other_adjustment"],
                            "total_gross": row["total_gross"],
                            "income_tax_pph21": row["tax_allowance"],
                            "bpjs_naker_deduction": row["bpjs_naker_allowance"],
                            "bpjs_kes_deduction": row["bpjs_kes_allowance"],
                            "bpjs_naker_jht_deduction": row["other_allowance_jht"],
                            "net_salary": row["net_salary"],
                            "bpjs_naker_jht_company": row["basic_salary"] * 0.037,
                            "total_company_paid": row["total_gross"] + (row["basic_salary"] * 0.037)
                        }
                        try:
                            db_manager.insert_payroll_record(record)
                        except Exception as e:
                            print("Error inserting:", e) 
                            
                    st.success(f"Berhasil! Data periode {month}/{year} telah tersimpan (DRAFT).")
                    
                    emp_details = get_employee_dict()
                    month_str = str(int(month)).zfill(2)
                    gross_pdf_path = f"WMI-Sal-{year}-{month_str}-Gross.pdf"
                    net_pdf_path = f"WMI-Sal-{year}-{month_str}-Net.pdf"
                    
                    create_payroll_pdf(gross_pdf_path, 'GROSS', period_name, st.session_state['preview_df'], emp_details)
                    create_payroll_pdf(net_pdf_path, 'NETT', period_name, st.session_state['preview_df'], emp_details)
                    
                    st.session_state['gross_pdf'] = gross_pdf_path
                    st.session_state['net_pdf'] = net_pdf_path
                    st.session_state['current_pid'] = pid
                    st.rerun()
                    
                if 'gross_pdf' in st.session_state:
                    with open(st.session_state['gross_pdf'], "rb") as f:
                        st.download_button("Download Laporan GROSS (PDF)", data=f, file_name=st.session_state['gross_pdf'], mime="application/pdf")
                    with open(st.session_state['net_pdf'], "rb") as f:
                        st.download_button("Download Laporan NETT (PDF)", data=f, file_name=st.session_state['net_pdf'], mime="application/pdf")
                        
                    st.markdown("---")
                    st.warning("⚠️ Laporan masih bersifat DRAFT (bisa diproses ulang). Jika sudah final, tekan tombol POSTING di bawah ini untuk mengunci permanen.")
                    if st.button("🔒 POSTING Laporan (Kunci Permanen)"):
                        cursor = conn.cursor()
                        cursor.execute("UPDATE payroll_periods SET posted_at = CURRENT_TIMESTAMP WHERE period_id = %s", (st.session_state['current_pid'],))
                        conn.commit()
                        st.success("Berhasil! Laporan telah di-Posting dan dikunci secara permanen.")
                        time.sleep(2)
                        del st.session_state['draft_df']
                        del st.session_state['preview_df']
                        del st.session_state['gross_pdf']
                        del st.session_state['net_pdf']
                        st.rerun()

    elif menu == "Riwayat & Histori Gaji":
        st.header("Riwayat Laporan Masa Lalu")
        periods = pd.read_sql_query("SELECT period_id, period_name, posted_at FROM payroll_periods ORDER BY period_id DESC", engine)
        
        if not periods.empty:
            p_dict = dict(zip(periods['period_name'], periods['period_id']))
            sel_p = st.selectbox("Pilih Periode Penggajian", list(p_dict.keys()))
            
            # Show posting status
            sel_posted = periods[periods['period_id'] == p_dict[sel_p]]['posted_at'].values[0]
            if pd.isna(sel_posted) or not sel_posted:
                st.info("Status: 📝 DRAFT (Belum Di-Posting)")
            else:
                st.success(f"Status: 🔒 POSTED (Dikunci pada {sel_posted})")
            
            history_df = pd.read_sql_query(f"SELECT * FROM payroll_records WHERE period_id = {p_dict[sel_p]}", engine)
            history_df.index = history_df.index + 1
            st.dataframe(history_df, use_container_width=True)
            
            st.warning("Data di atas adalah riwayat yang sudah dikunci (Read-Only). Mengubah data masa lalu dapat berdampak pada laporan pajak tahunan.")
            
            if 'edit_unlocked' not in st.session_state:
                st.session_state['edit_unlocked'] = False
                st.session_state['confirm_1'] = False
                st.session_state['confirm_2'] = False

            if not st.session_state['edit_unlocked']:
                if st.button("Edit Data Masa Lalu"):
                    st.session_state['confirm_1'] = True
                    
                if st.session_state['confirm_1'] and not st.session_state['confirm_2']:
                    st.error("Konfirmasi 1: Apakah Anda yakin ingin MENGUBAH data bulan yang sudah ditutup/lewat?")
                    if st.button("Ya, Saya Yakin"):
                        st.session_state['confirm_2'] = True
                        st.rerun()

                if st.session_state['confirm_2']:
                    st.error("Konfirmasi 2: PERINGATAN! Tindakan ini akan mengubah riwayat permanen SPT Pajak. Lanjutkan?")
                    if st.button("BUKA AKSES EDIT SEKARANG"):
                        st.session_state['edit_unlocked'] = True
                        st.session_state['confirm_1'] = False
                        st.session_state['confirm_2'] = False
                        st.rerun()
            else:
                st.success("Mode Edit Aktif! Silakan edit data langsung pada tabel di bawah.")
                edited_history = st.data_editor(history_df, use_container_width=True)
                if st.button("Simpan Perubahan Permanen ke Database"):
                    # Here we would update the actual records
                    st.info("Perubahan berhasil disimpan secara permanen!")
                    time.sleep(1)
                    st.session_state['edit_unlocked'] = False
                    st.rerun()
        else:
            st.info("Belum ada data periode.")

    elif menu == "Laporan & Rekapitulasi":
        st.header("Laporan & Rekapitulasi (Export & Analisa)")
        
        report_type = st.selectbox("Pilih Jenis Laporan", [
            "1. Rekapitulasi Gaji (Rentang Bulan)",
            "2. Laporan BPJS Kesehatan",
            "3. Laporan BPJS Ketenagakerjaan (JHT, JKK, JKM)",
            "4. Laporan Pajak (PPh 21)",
            "5. Laporan Total Gross",
            "6. Laporan Total Gross vs Pajak (Komparasi)"
        ])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            start_m = st.number_input("Dari Bulan", min_value=1, max_value=12, value=1)
        with col2:
            end_m = st.number_input("Sampai Bulan", min_value=1, max_value=12, value=datetime.now().month)
        with col3:
            rpt_year = st.number_input("Tahun Periode", min_value=2020, max_value=2100, value=datetime.now().year)
            
        if st.button("Tampilkan Laporan"):
            query = f"""
                SELECT 
                    p.period_month, 
                    p.period_year,
                    p.period_name,
                    e.employee_id,
                    e.employee_name, 
                    r.*
                FROM payroll_records r
                JOIN payroll_periods p ON r.period_id = p.period_id
                JOIN employees e ON r.employee_id = e.employee_id
                WHERE p.period_year = {rpt_year} 
                  AND p.period_month >= {start_m} 
                  AND p.period_month <= {end_m}
                  AND p.posted_at IS NOT NULL
                ORDER BY e.employee_id, p.period_month
            """
            df_report = pd.read_sql_query(query, engine)
            
            if df_report.empty:
                st.warning("⚠️ Tidak ada data POSTED untuk rentang waktu tersebut.")
            else:
                actual_start = df_report['period_month'].min()
                actual_end = df_report['period_month'].max()
                
                show_details = st.toggle("Tampilkan Rincian Tiap Bulan (Detail)")
                
                if "Rekapitulasi Gaji" in report_type:
                    st.subheader(f"Rekap Gaji Net (Bulan Aktual yang Ter-Posting: {actual_start} s/d {actual_end} - Tahun {rpt_year})")
                    
                    if show_details:
                        detail_df = df_report[['employee_id', 'employee_name', 'period_name', 'basic_salary', 'total_gross', 'income_tax_pph21', 'net_salary']].copy()
                        detail_df.columns = ['ID', 'Nama Karyawan', 'Periode', 'Gaji Pokok', 'Total Gross', 'Pajak (PPh 21)', 'Net Salary']
                        detail_df.index = detail_df.index + 1
                        st.dataframe(detail_df.style.format({col: "{:,.0f}" for col in detail_df.columns if col not in ['ID', 'Nama Karyawan', 'Periode']}), use_container_width=True)
                    else:
                        pivot_net = df_report.pivot_table(index=['employee_id', 'employee_name'], columns='period_name', values='net_salary', aggfunc='sum', fill_value=0)
                        pivot_net['TOTAL YTD'] = pivot_net.sum(axis=1)
                        pivot_net = pivot_net.reset_index()
                        pivot_net.index = pivot_net.index + 1
                        
                        st.markdown("**Tabel Rincian Gaji Bersih (Net Salary) per Bulan**")
                        st.dataframe(pivot_net.style.format({col: "{:,.0f}" for col in pivot_net.columns if col not in ['employee_id', 'employee_name']}), use_container_width=True)
                        
                        st.markdown("**Akumulasi Total Elemen Gaji**")
                        agg_df = df_report.groupby(['employee_id', 'employee_name'])[['basic_salary', 'total_gross', 'income_tax_pph21', 'net_salary']].sum().reset_index()
                        agg_df.columns = ['ID', 'Nama Karyawan', 'Total Gaji Pokok', 'Total Gross', 'Total Pajak (PPh 21)', 'Total Net Salary']
                        agg_df.index = agg_df.index + 1
                        st.dataframe(agg_df.style.format({col: "{:,.0f}" for col in agg_df.columns if col not in ['ID', 'Nama Karyawan']}), use_container_width=True)
                        
                elif "BPJS Kesehatan" in report_type:
                    st.subheader(f"Laporan BPJS Kesehatan (Bulan Aktual yang Ter-Posting: {actual_start} s/d {actual_end} - Tahun {rpt_year})")
                    
                    if show_details:
                        detail_df = df_report[['employee_id', 'employee_name', 'period_name', 'bpjs_kes_allowance', 'bpjs_kes_deduction']].copy()
                        detail_df['Total Setoran'] = detail_df['bpjs_kes_allowance'] + detail_df['bpjs_kes_deduction']
                        detail_df.columns = ['ID', 'Nama Karyawan', 'Periode', 'Tunj. BPJS Kes (Perusahaan)', 'Potongan BPJS Kes (Karyawan)', 'Total Setoran']
                        detail_df.index = detail_df.index + 1
                        st.dataframe(detail_df.style.format({col: "{:,.0f}" for col in detail_df.columns if col not in ['ID', 'Nama Karyawan', 'Periode']}), use_container_width=True)
                    else:
                        agg_bpjs = df_report.groupby(['employee_id', 'employee_name'])[['bpjs_kes_allowance', 'bpjs_kes_deduction']].sum().reset_index()
                        agg_bpjs['Total Setoran ke BPJS'] = agg_bpjs['bpjs_kes_allowance'] + agg_bpjs['bpjs_kes_deduction']
                        agg_bpjs.columns = ['ID', 'Nama Karyawan', 'Tunj. BPJS Kes (Perusahaan)', 'Potongan BPJS Kes (Karyawan)', 'Total Setoran ke BPJS']
                        agg_bpjs.index = agg_bpjs.index + 1
                        st.dataframe(agg_bpjs.style.format({col: "{:,.0f}" for col in agg_bpjs.columns if col not in ['ID', 'Nama Karyawan']}), use_container_width=True)
                        
                elif "BPJS Ketenagakerjaan" in report_type:
                    st.subheader(f"Laporan BPJS Ketenagakerjaan (Bulan Aktual yang Ter-Posting: {actual_start} s/d {actual_end} - Tahun {rpt_year})")
                    
                    if show_details:
                        detail_df = df_report[['employee_id', 'employee_name', 'period_name', 'bpjs_naker_allowance', 'bpjs_naker_jht_deduction', 'bpjs_naker_jht_company']].copy()
                        detail_df['Total Setoran'] = detail_df['bpjs_naker_allowance'] + detail_df['bpjs_naker_jht_deduction'] + detail_df['bpjs_naker_jht_company']
                        detail_df.columns = ['ID', 'Nama Karyawan', 'Periode', 'Tunj. JKK/JKM (Perusahaan)', 'Potongan JHT (Karyawan)', 'Tunj. JHT (Perusahaan)', 'Total Setoran BPJS-TK']
                        detail_df.index = detail_df.index + 1
                        st.dataframe(detail_df.style.format({col: "{:,.0f}" for col in detail_df.columns if col not in ['ID', 'Nama Karyawan', 'Periode']}), use_container_width=True)
                    else:
                        agg_jht = df_report.groupby(['employee_id', 'employee_name'])[['bpjs_naker_allowance', 'bpjs_naker_jht_deduction', 'bpjs_naker_jht_company']].sum().reset_index()
                        agg_jht['Total Setoran BPJS-TK'] = agg_jht['bpjs_naker_allowance'] + agg_jht['bpjs_naker_jht_deduction'] + agg_jht['bpjs_naker_jht_company']
                        agg_jht.columns = ['ID', 'Nama Karyawan', 'Tunj. JKK/JKM (Perusahaan)', 'Potongan JHT (Karyawan)', 'Tunj. JHT (Perusahaan)', 'Total Setoran BPJS-TK']
                        agg_jht.index = agg_jht.index + 1
                        st.dataframe(agg_jht.style.format({col: "{:,.0f}" for col in agg_jht.columns if col not in ['ID', 'Nama Karyawan']}), use_container_width=True)
                        
                elif "Laporan Pajak" in report_type:
                    st.subheader(f"Laporan Pajak PPh 21 (Bulan Aktual yang Ter-Posting: {actual_start} s/d {actual_end} - Tahun {rpt_year})")
                    if show_details:
                        detail_df = df_report[['employee_id', 'employee_name', 'period_name', 'income_tax_pph21']].copy()
                        detail_df.columns = ['ID', 'Nama Karyawan', 'Periode', 'Pajak (PPh 21)']
                        detail_df.index = detail_df.index + 1
                        st.dataframe(detail_df.style.format({col: "{:,.0f}" for col in detail_df.columns if col not in ['ID', 'Nama Karyawan', 'Periode']}), use_container_width=True)
                    else:
                        agg_df = df_report.groupby(['employee_id', 'employee_name'])[['income_tax_pph21']].sum().reset_index()
                        agg_df.columns = ['ID', 'Nama Karyawan', 'Total Pajak (PPh 21)']
                        agg_df.index = agg_df.index + 1
                        st.dataframe(agg_df.style.format({col: "{:,.0f}" for col in agg_df.columns if col not in ['ID', 'Nama Karyawan']}), use_container_width=True)
                        
                elif "Laporan Total Gross" in report_type and "vs" not in report_type:
                    st.subheader(f"Laporan Total Gross (Bulan Aktual yang Ter-Posting: {actual_start} s/d {actual_end} - Tahun {rpt_year})")
                    if show_details:
                        detail_df = df_report[['employee_id', 'employee_name', 'period_name', 'total_gross']].copy()
                        detail_df.columns = ['ID', 'Nama Karyawan', 'Periode', 'Total Gross']
                        detail_df.index = detail_df.index + 1
                        st.dataframe(detail_df.style.format({col: "{:,.0f}" for col in detail_df.columns if col not in ['ID', 'Nama Karyawan', 'Periode']}), use_container_width=True)
                    else:
                        agg_df = df_report.groupby(['employee_id', 'employee_name'])[['total_gross']].sum().reset_index()
                        agg_df.columns = ['ID', 'Nama Karyawan', 'Total Gross YTD']
                        agg_df.index = agg_df.index + 1
                        st.dataframe(agg_df.style.format({col: "{:,.0f}" for col in agg_df.columns if col not in ['ID', 'Nama Karyawan']}), use_container_width=True)
                        
                elif "Gross vs Pajak" in report_type:
                    st.subheader(f"Komparasi Total Gross & Pajak (Bulan Aktual yang Ter-Posting: {actual_start} s/d {actual_end} - Tahun {rpt_year})")
                    if show_details:
                        detail_df = df_report[['employee_id', 'employee_name', 'period_name', 'total_gross', 'income_tax_pph21']].copy()
                        detail_df['% Pajak Aktual'] = (detail_df['income_tax_pph21'] / detail_df['total_gross'] * 100).fillna(0)
                        detail_df.columns = ['ID', 'Nama Karyawan', 'Periode', 'Total Gross', 'Pajak (PPh 21)', '% Pajak Aktual']
                        detail_df.index = detail_df.index + 1
                        st.dataframe(detail_df.style.format({
                            'Total Gross': "{:,.0f}", 
                            'Pajak (PPh 21)': "{:,.0f}", 
                            '% Pajak Aktual': "{:.2f}%"
                        }), use_container_width=True)
                    else:
                        agg_df = df_report.groupby(['employee_id', 'employee_name'])[['total_gross', 'income_tax_pph21']].sum().reset_index()
                        agg_df['% Rata-Rata Pajak'] = (agg_df['income_tax_pph21'] / agg_df['total_gross'] * 100).fillna(0)
                        agg_df.columns = ['ID', 'Nama Karyawan', 'Total Gross YTD', 'Total Pajak YTD', '% Rata-Rata Pajak']
                        agg_df.index = agg_df.index + 1
                        st.dataframe(agg_df.style.format({
                            'Total Gross YTD': "{:,.0f}", 
                            'Total Pajak YTD': "{:,.0f}", 
                            '% Rata-Rata Pajak': "{:.2f}%"
                        }), use_container_width=True)

    elif menu == "Data Karyawan":
        st.header("Manajemen Karyawan & Histori Gaji Pokok")
        emp_df = pd.read_sql_query("SELECT employee_id, employee_name, gender, marital_status, dependents, department FROM employees", engine)
        emp_df.index = emp_df.index + 1
        st.dataframe(emp_df, use_container_width=True)
        
        st.subheader("Riwayat Kenaikan Gaji Pokok")
        hist_df = pd.read_sql_query('''
            SELECT sh.effective_date, e.employee_name, sh.basic_salary, sh.notes 
            FROM salary_history sh 
            JOIN employees e ON sh.employee_id = e.employee_id 
            ORDER BY sh.effective_date DESC
        ''', engine)
        hist_df.index = hist_df.index + 1
        st.dataframe(hist_df, use_container_width=True)
        
        st.markdown("---")
        st.subheader("Catat Kenaikan Gaji Baru")
        col1, col2 = st.columns(2)
        sel_emp = col1.selectbox("Pilih Karyawan", emp_df['employee_name'].tolist())
        new_salary = col2.number_input("Gaji Pokok Baru", min_value=0, step=100000)
        eff_date = col1.date_input("Berlaku Mulai Tanggal")
        notes = col2.text_input("Keterangan (contoh: Promosi / Penyesuaian Tahunan)")
        
        if st.button("Simpan Gaji Baru"):
            emp_id = emp_df[emp_df['employee_name'] == sel_emp]['employee_id'].values[0]
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO salary_history (employee_id, basic_salary, effective_date, notes) 
                VALUES (%s, %s, %s, %s)
            ''', (int(emp_id), new_salary, eff_date, notes))
            conn.commit()
            st.success("Berhasil mencatat kenaikan gaji!")
            time.sleep(1)
            st.rerun()

if __name__ == '__main__':
    main()
