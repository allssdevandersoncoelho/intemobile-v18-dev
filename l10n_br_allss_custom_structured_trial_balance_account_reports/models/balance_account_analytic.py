import re
import logging

from odoo import fields, models, api, _, tools
from .allss_funtions import account_analytic_def
import odoo.addons.decimal_precision as dp

_logger = logging.getLogger(__name__)


class BalanceAccountAnalytic(models.Model):
    _name = "allss.balance.account.analytic"
    _description = "Balancete Estruturado Contas Analiticas"
    _order = "allss_company_id, allss_date, allss_account_analytic_id, allss_account_id"

    allss_company_id = fields.Many2one('res.company', string='Empresa', store=True, index=True)

    allss_parent_id_6 = fields.Many2one('account.group', string='1º Nível', store=True, index=True)
    allss_parent_id_5 = fields.Many2one('account.group', string='2º Nível', store=True, index=True)
    allss_parent_id_4 = fields.Many2one('account.group', string='3º Nível', store=True, index=True)
    allss_parent_id_3 = fields.Many2one('account.group', string='4º Nível', store=True, index=True)
    allss_group_id = fields.Many2one('account.group', string='5º Nível', store=True, index=True)

    allss_account_id = fields.Many2one('account.account', string='Conta', store=True, index=True)

    allss_account_analytic_id = fields.Many2one('account.analytic.account', string='Conta Analítica', store=True,index=True)
    allss_analytic_plan_id = fields.Many2one('account.analytic.plan', string='Plano Analítico', store=True,index=True)

    allss_date = fields.Date("Data", store=True, index=True)

    allss_previous_balance = fields.Float("Saldo Anterior", store=True, index=True, digits=dp.get_precision('Account Balance'))
    allss_debit = fields.Float("Débito", store=True, index=True, digits=dp.get_precision('Account Balance'))
    allss_credit = fields.Float("Crédito", store=True, index=True, digits=dp.get_precision('Account Balance'))
    allss_final_balance = fields.Float("Saldo Atual", store=True, index=True, digits=dp.get_precision('Account Balance'))



    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        result = super(BalanceAccountAnalytic, self).read_group(
            domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy
        )

        if not result or not fields:
            return result

        for group_line in result:
            domain_line = group_line.get("__domain", [])
            try:
                # Busca a menor data dentro do domínio do grupo
                where_calc = self._where_calc(domain_line)
                query_obj = getattr(where_calc, "query", None)

                if not query_obj:
                    continue

                query_sql = str(query_obj)
                params = getattr(query_obj, "params", [])

                self.env.cr.execute(f"""
                    SELECT MIN(allss_date) AS first_date
                    FROM allss_balance_account_analytic
                    WHERE {query_sql}
                """, params)
                row = self.env.cr.dictfetchone()
                first_date = row.get("first_date") if row else None

                prev_balance = 0
                if first_date:
                    self.env.cr.execute(f"""
                        SELECT allss_final_balance
                        FROM allss_balance_account_analytic
                        WHERE allss_date < %s
                        AND {query_sql}
                        ORDER BY allss_date DESC
                        LIMIT 1
                    """, [first_date] + params)
                    row_prev = self.env.cr.dictfetchone()
                    prev_balance = row_prev.get("allss_final_balance", 0) if row_prev else 0

                group_line["allss_previous_balance"] = prev_balance
                group_line["allss_final_balance"] = (
                    prev_balance
                    + group_line.get("allss_debit", 0)
                    - group_line.get("allss_credit", 0)
                )

            except Exception as e:
                _logger.error("Erro ao processar grupo %s: %s", group_line, e)

        return result

     
    def open_document(self, options=None, params=None):

        domain = ['&',
                  ('date', '=', self.allss_date),
                  ('account_id', '=', self.allss_account_id.id)
                  ]

        dict_ret = {'type': 'ir.actions.act_window',
                    'name': f'Balancete Estruturado - Conta: {self.allss_account_id.id} - Data: {self.allss_date}',
                    'res_model': 'account.move.line',
                    # 'view_type': 'tree',
                    'view_mode': 'list,pivot,kanban,graph,form',
                    'domain': domain
                    }

        return dict_ret






    # def execute_sql(self):
    #     cr = self._cr

    #     cr.execute("DELETE FROM allss_balance_account_analytic;")

    #     account_analytic_id, analytic_plan_id = account_analytic_def(self)

    #     account_analytic_id_sql = (
    #         str(account_analytic_id) if account_analytic_id else 'NULL'
    #     )

    #     sql = f"""
    #     WITH aml_expanded AS (
    #         SELECT
    #             aml.company_id,
    #             aml.account_id,
    #             aml.date::date AS date,

    #             /* Analítica vinda do json OU padrão */
    #             COALESCE(ad.analytic_account_id, {account_analytic_id_sql}) AS analytic_account_id,

    #             aml.debit,
    #             aml.credit
    #         FROM account_move_line aml
    #         JOIN account_move am
    #             ON am.id = aml.move_id
    #         AND am.state = 'posted'

    #         LEFT JOIN LATERAL (
    #             SELECT key::int AS analytic_account_id
    #             FROM jsonb_each(aml.analytic_distribution)
    #         ) ad ON aml.analytic_distribution IS NOT NULL
    #     ),

    #     aml_grouped AS (
    #         SELECT
    #             company_id,
    #             account_id,
    #             analytic_account_id,
    #             date,
    #             SUM(debit) AS debit,
    #             SUM(credit) AS credit
    #         FROM aml_expanded
    #         GROUP BY
    #             company_id,
    #             account_id,
    #             analytic_account_id,
    #             date
    #     ),

    #     aml_balance AS (
    #         SELECT
    #             g.*,
    #             SUM(g.debit - g.credit) OVER (
    #                 PARTITION BY
    #                     g.company_id,
    #                     g.account_id,
    #                     g.analytic_account_id
    #                 ORDER BY g.date
    #             ) AS final_balance
    #         FROM aml_grouped g
    #     ),

    #     aml_final AS (
    #         SELECT
    #             *,
    #             LAG(final_balance, 1, 0) OVER (
    #                 PARTITION BY
    #                     company_id,
    #                     account_id,
    #                     analytic_account_id
    #                 ORDER BY date
    #             ) AS previous_balance
    #         FROM aml_balance
    #     )

    #     INSERT INTO allss_balance_account_analytic (
    #         id,
    #         create_uid,
    #         create_date,
    #         write_uid,
    #         write_date,
    #         allss_company_id,
    #         allss_account_id,
    #         allss_account_analytic_id,
    #         allss_date,
    #         allss_previous_balance,
    #         allss_debit,
    #         allss_credit,
    #         allss_final_balance
    #     )
    #     SELECT
    #         row_number() OVER () AS id,
    #         1,
    #         CURRENT_DATE,
    #         1,
    #         CURRENT_DATE,
    #         f.company_id,
    #         f.account_id,
    #         f.analytic_account_id,
    #         f.date,
    #         f.previous_balance,
    #         f.debit,
    #         f.credit,
    #         f.final_balance
    #     FROM aml_final f;
    #     """

    #     cr.execute(sql)

    #     cr.execute("""
    #         SELECT setval(
    #             'allss_balance_account_analytic_id_seq',
    #             COALESCE((SELECT MAX(id) FROM allss_balance_account_analytic), 0) + 1,
    #             false
    #         );
    #     """)



    def execute_sql(self):
        cr = self._cr

        cr.execute("DELETE FROM allss_balance_account_analytic;")

        account_analytic_id, analytic_plan_id = account_analytic_def(self)
        account_analytic_id_sql = str(account_analytic_id) if account_analytic_id else 'NULL'

        sql = f"""
        WITH aml_expanded AS (
            SELECT
                aml.company_id,
                aml.account_id,
                aml.date::date AS date,
                COALESCE(ad.account_id, {account_analytic_id_sql}) AS analytic_account_id,
                aml.debit,
                aml.credit
            FROM account_move_line aml
            JOIN account_move am
                ON am.id = aml.move_id
                AND am.state = 'posted'
            LEFT JOIN LATERAL (
                SELECT (jsonb_object_keys(aml.analytic_distribution))::int AS account_id
            ) ad ON TRUE
        ),

        aml_grouped AS (
            SELECT
                company_id,
                account_id,
                analytic_account_id,
                date,
                SUM(debit) AS debit,
                SUM(credit) AS credit
            FROM aml_expanded
            GROUP BY
                company_id,
                account_id,
                analytic_account_id,
                date
        ),

        aml_balance AS (
            SELECT
                g.*,
                SUM(g.debit - g.credit) OVER (
                    PARTITION BY g.company_id, g.account_id, g.analytic_account_id
                    ORDER BY g.date
                ) AS final_balance
            FROM aml_grouped g
        ),

        aml_final AS (
            SELECT
                b.*,
                LAG(final_balance, 1, 0) OVER (
                    PARTITION BY company_id, account_id, analytic_account_id
                    ORDER BY date
                ) AS previous_balance,
                acc.parent_id AS allss_parent_id_6,
                acc2.parent_id AS allss_parent_id_5,
                acc3.parent_id AS allss_parent_id_4,
                acc4.parent_id AS allss_parent_id_3,
                acc5.parent_id AS allss_group_id,
                (
                    SELECT plan_id
                    FROM account_analytic_account x
                    WHERE x.id = b.analytic_account_id
                ) AS analytic_plan_id
            FROM aml_balance b
            JOIN account_account acc ON acc.id = b.account_id
            LEFT JOIN account_account acc2 ON acc2.id = acc.parent_id
            LEFT JOIN account_account acc3 ON acc3.id = acc2.parent_id
            LEFT JOIN account_account acc4 ON acc4.id = acc3.parent_id
            LEFT JOIN account_account acc5 ON acc5.id = acc4.parent_id
        )

        INSERT INTO allss_balance_account_analytic (
            id,
            create_uid,
            create_date,
            write_uid,
            write_date,
            allss_company_id,
            allss_account_id,
            allss_account_analytic_id,
            allss_analytic_plan_id,
            allss_date,
            allss_previous_balance,
            allss_debit,
            allss_credit,
            allss_final_balance,
            allss_group_id,
            allss_parent_id_3,
            allss_parent_id_4,
            allss_parent_id_5,
            allss_parent_id_6
        )
        SELECT
            row_number() OVER () AS id,
            1,
            CURRENT_DATE,
            1,
            CURRENT_DATE,
            f.company_id,
            f.account_id,
            f.analytic_account_id,
            f.analytic_plan_id,
            f.date,
            f.previous_balance,
            f.debit,
            f.credit,
            f.final_balance,
            f.allss_group_id,
            f.allss_parent_id_3,
            f.allss_parent_id_4,
            f.allss_parent_id_5,
            f.allss_parent_id_6
        FROM aml_final f;
        """

        cr.execute(sql)

        cr.execute("""
            BEGIN;
                LOCK TABLE allss_balance_account_analytic IN EXCLUSIVE MODE;
                SELECT setval(
                    'allss_balance_account_analytic_id_seq',
                    COALESCE((SELECT MAX(id) FROM allss_balance_account_analytic), 0) + 1,
                    false
                );
            COMMIT;
        """)













    def init_account_analytic(self):
        account_analytic_id = int(account_analytic_def(self)[0] or 0)
        self._cr.execute(f"""
            SELECT DISTINCT
                aml.company_id,
                aml.account_id,
                COALESCE(kv.key::int, {account_analytic_id}) AS analytic_account_id,
                (
                    SELECT plan_id
                    FROM account_analytic_account x
                    WHERE x.id = COALESCE(kv.key::int, {account_analytic_id})
                ) AS analytic_plan_id,
                DATE_TRUNC('month', aml.date)::date AS month_date
            FROM account_move_line aml
            LEFT JOIN LATERAL jsonb_each(aml.analytic_distribution::jsonb) AS kv(key, value)
                ON aml.analytic_distribution IS NOT NULL
            WHERE aml.date >= DATE_TRUNC('month', CURRENT_DATE)
            AND aml.date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
        """)

        for row in self._cr.fetchall():
            company_id, account_id, analytic_id, plan_id, month_date = row
            analytic_id = analytic_id or account_analytic_id

            existing = self.env['allss.balance.account.analytic'].search([
                ('allss_company_id', '=', company_id),
                ('allss_account_id', '=', account_id),
                ('allss_account_analytic_id', '=', analytic_id),
                ('allss_date', '=', month_date)
            ], limit=1)

            if not existing:
                # Busca saldo anterior (último mês)
                prev = self.env['allss.balance.account.analytic'].search([
                    ('allss_company_id', '=', company_id),
                    ('allss_account_id', '=', account_id),
                    ('allss_account_analytic_id', '=', analytic_id),
                    ('allss_date', '<', month_date)
                ], limit=1, order='allss_date desc')

                # Hierarquia da conta
                account = self.env['account.account'].browse(account_id)
                group = account.group_id
                parent3 = group.parent_id if group else False
                parent4 = parent3.parent_id if parent3 else False
                parent5 = parent4.parent_id if parent4 else False
                parent6 = parent5.parent_id if parent5 else False

                vals = {
                    'allss_company_id': company_id, 
                    'allss_account_id': account_id,
                    'allss_account_analytic_id': analytic_id,
                    'allss_analytic_plan_id': plan_id,
                    'allss_date': month_date,
                    'allss_debit': 0.0,
                    'allss_credit': 0.0,
                    'allss_previous_balance': prev.allss_final_balance if prev else 0.0,
                    'allss_final_balance': prev.allss_final_balance if prev else 0.0,
                    'allss_group_id': group.id if group else False,
                    'allss_parent_id_3': parent3.id if parent3 else False,
                    'allss_parent_id_4': parent4.id if parent4 else False,
                    'allss_parent_id_5': parent5.id if parent5 else False,
                    'allss_parent_id_6': parent6.id if parent6 else False,
                }

                self.env['allss.balance.account.analytic'].create(vals)
                self.env.cr.commit()
