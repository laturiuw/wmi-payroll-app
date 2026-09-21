import psycopg2

NEON_URL = "postgresql://neondb_owner:npg_QB2MingP1ESe@ep-restless-glitter-b3dve2td-pooler.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

class PayrollDB:
    def __init__(self, db_path='payroll.db'):
        # db_path is ignored, we connect directly to Neon PostgreSQL
        self.conn_str = NEON_URL

    def _get_conn(self):
        return psycopg2.connect(self.conn_str)

    def get_or_create_period(self, month, year, month_days, period_name):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT period_id FROM payroll_periods WHERE period_month = %s AND period_year = %s', (month, year))
        row = cursor.fetchone()
        
        if row:
            period_id = row[0]
        else:
            cursor.execute('''
                INSERT INTO payroll_periods (period_month, period_year, period_name)
                VALUES (%s, %s, %s) RETURNING period_id
            ''', (month, year, period_name))
            period_id = cursor.fetchone()[0]
            conn.commit()
            
        conn.close()
        return period_id
        
    def insert_payroll_record(self, record):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO payroll_records (
                employee_id, period_id, work_days, thr_months,
                basic_salary, base_pay, functional_allowance, selling_commission,
                transport_allowance, other_allowance_jht, bpjs_naker_allowance,
                bpjs_kes_allowance, sub_gross, tax_allowance, bonus, thr,
                other_adjustment, total_gross, income_tax_pph21,
                bpjs_naker_deduction, bpjs_kes_deduction, bpjs_naker_jht_deduction,
                net_salary, bpjs_naker_jht_company, total_company_paid
            ) VALUES (
                %(employee_id)s, %(period_id)s, %(work_days)s, %(thr_months)s,
                %(basic_salary)s, %(base_pay)s, %(functional_allowance)s, %(selling_commission)s,
                %(transport_allowance)s, %(other_allowance_jht)s, %(bpjs_naker_allowance)s,
                %(bpjs_kes_allowance)s, %(sub_gross)s, %(tax_allowance)s, %(bonus)s, %(thr)s,
                %(other_adjustment)s, %(total_gross)s, %(income_tax_pph21)s,
                %(bpjs_naker_deduction)s, %(bpjs_kes_deduction)s, %(bpjs_naker_jht_deduction)s,
                %(net_salary)s, %(bpjs_naker_jht_company)s, %(total_company_paid)s
            )
        ''', record)
        
        conn.commit()
        conn.close()
