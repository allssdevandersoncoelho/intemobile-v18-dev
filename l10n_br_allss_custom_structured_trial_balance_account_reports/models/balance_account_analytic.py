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
    #     # Limpa a tabela antes de inserir
    #     self._cr.execute("DELETE FROM public.allss_balance_account_analytic;")
        
    #     # ID da conta analítica padrão (pode ser None)
    #     account_analytic_id = account_analytic_def(self)[0] or 'NULL'

    #     sql = f"""
    #     WITH
    #     -- Linhas com distribuição analítica
    #     dist AS (
    #         SELECT
    #             aml.company_id,
    #             aml.account_id,
    #             NULLIF((kv.key)::int, 0) AS analytic_account_id,  -- evita ID=0
    #             (kv.value)::numeric AS weight,
    #             aml.debit,
    #             aml.credit,
    #             aml.date
    #         FROM account_move_line aml
    #         CROSS JOIN LATERAL jsonb_each(aml.analytic_distribution::jsonb) AS kv(key, value)
    #         WHERE aml.analytic_distribution IS NOT NULL
    #         AND aml.analytic_distribution::text <> '{{}}'
    #     ),

    #     -- Linhas sem distribuição, atribuídas a conta analítica padrão OU NULL
    #     nodist AS (
    #         SELECT
    #             aml.company_id,
    #             aml.account_id,
    #             NULLIF({account_analytic_id}, 0)::int AS analytic_account_id,  -- nunca 0
    #             1.0::numeric AS weight,
    #             aml.debit,
    #             aml.credit,
    #             aml.date
    #         FROM account_move_line aml
    #         WHERE aml.analytic_distribution IS NULL
    #         OR aml.analytic_distribution::text = '{{}}'
    #     ),

    #     -- Une todas as linhas
    #     all_rows AS (
    #         SELECT * FROM dist
    #         UNION ALL
    #         SELECT * FROM nodist
    #     ),

    #     -- Mantém SOMENTE IDs válidos que existam em account_analytic_account
    #     valid_rows AS (
    #         SELECT
    #             r.*
    #         FROM all_rows r
    #         LEFT JOIN account_analytic_account aac
    #             ON aac.id = r.analytic_account_id
    #         WHERE r.analytic_account_id IS NULL
    #         OR aac.id IS NOT NULL  -- garante FK existente
    #     ),

    #     -- Aplica o peso
    #     normalized AS (
    #         SELECT
    #             company_id,
    #             account_id,
    #             analytic_account_id,
    #             date,
    #             debit,
    #             credit,
    #             CASE WHEN weight > 1 THEN weight / 100.0 ELSE weight END AS normalized_weight
    #         FROM valid_rows
    #     ),

    #     -- Soma por linha de data real (não só por mês)
    #     summed AS (
    #         SELECT
    #             company_id,
    #             account_id,
    #             analytic_account_id,
    #             date,
    #             SUM(debit * normalized_weight) AS debit,
    #             SUM(credit * normalized_weight) AS credit
    #         FROM normalized
    #         GROUP BY company_id, account_id, analytic_account_id, date
    #     ),

    #     -- Calcula o saldo final acumulado
    #     balances AS (
    #         SELECT
    #             company_id AS allss_company_id,
    #             account_id AS allss_account_id,
    #             analytic_account_id AS allss_account_analytic_id,
    #             debit AS allss_debit,
    #             credit AS allss_credit,
    #             date AS allss_date,
    #             SUM(debit - credit) OVER (
    #                 PARTITION BY company_id, account_id, analytic_account_id
    #                 ORDER BY date, account_id
    #                 ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    #             ) AS allss_final_balance
    #         FROM summed
    #     ),

    #     -- Calcula saldo anterior (previous_balance)
    #     with_prev AS (
    #         SELECT
    #             b.*,
    #             LAG(allss_final_balance, 1, 0) OVER (
    #                 PARTITION BY allss_company_id, allss_account_id, allss_account_analytic_id
    #                 ORDER BY allss_date, allss_account_id
    #             ) AS allss_previous_balance
    #         FROM balances b
    #     )

    #     -- Insere os resultados na tabela final
    #     INSERT INTO public.allss_balance_account_analytic (
    #         allss_company_id,
    #         allss_account_id,
    #         allss_account_analytic_id,
    #         allss_analytic_plan_id,
    #         allss_date,
    #         allss_debit,
    #         allss_credit,
    #         allss_previous_balance,
    #         allss_final_balance,
    #         allss_group_id,
    #         allss_parent_id_3,
    #         allss_parent_id_4,
    #         allss_parent_id_5,
    #         allss_parent_id_6
    #     )
    #     SELECT
    #         wp.allss_company_id,
    #         wp.allss_account_id,
    #         wp.allss_account_analytic_id,
    #         aac.plan_id AS allss_analytic_plan_id,
    #         wp.allss_date,
    #         wp.allss_debit,
    #         wp.allss_credit,
    #         wp.allss_previous_balance,
    #         wp.allss_final_balance,
    #         NULL AS allss_group_id,
    #         NULL AS allss_parent_id_3,
    #         NULL AS allss_parent_id_4,
    #         NULL AS allss_parent_id_5,
    #         NULL AS allss_parent_id_6
    #     FROM with_prev wp
    #     LEFT JOIN account_analytic_account aac
    #         ON aac.id = wp.allss_account_analytic_id
    #     ORDER BY wp.allss_company_id, wp.allss_account_id, wp.allss_account_analytic_id, wp.allss_date;
    #     """

    #     self._cr.execute(sql)

    #     # Atualiza sequência da tabela
    #     self._cr.execute("""
    #         BEGIN;
    #             LOCK TABLE allss_balance_account_analytic IN EXCLUSIVE MODE;
    #             SELECT setval(
    #                 'allss_balance_account_analytic_id_seq',
    #                 COALESCE((SELECT MAX(id)+1 FROM allss_balance_account_analytic), 1),
    #                 false
    #             );
    #         COMMIT;
    #     """)





    def execute_sql(self):
        cr = self._cr
        cr.execute("DELETE FROM allss_balance_account_analytic;")

        account_analytic_id = account_analytic_def(self)[0] or 0

        sql = f"""
        WITH base_moves AS (
            SELECT
                aml.company_id,
                aml.account_id,
                COALESCE(ad.account_id, {account_analytic_id}) AS analytic_account_id,
                aml.date,
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

        min_dates AS (
            SELECT
                company_id,
                account_id,
                analytic_account_id,
                MIN(date) AS min_date
            FROM base_moves
            GROUP BY company_id, account_id, analytic_account_id
        ),

        generated_months AS (
            SELECT
                md.company_id,
                md.account_id,
                md.analytic_account_id,
                generate_series(
                    date_trunc('month', md.min_date),
                    date_trunc('month', CURRENT_DATE),
                    '1 month'
                )::date AS date
            FROM min_dates md
        ),

        missing_months AS (
            SELECT
                gm.company_id,
                gm.account_id,
                gm.analytic_account_id,
                gm.date,
                0::numeric AS debit,
                0::numeric AS credit
            FROM generated_months gm
            LEFT JOIN base_moves bm
                ON bm.company_id = gm.company_id
            AND bm.account_id = gm.account_id
            AND bm.analytic_account_id = gm.analytic_account_id
            AND date_trunc('month', bm.date) = gm.date
            WHERE bm.date IS NULL
        ),

        real_moves AS (
            SELECT
                company_id,
                account_id,
                analytic_account_id,
                date,
                SUM(debit) AS debit,
                SUM(credit) AS credit
            FROM base_moves
            GROUP BY company_id, account_id, analytic_account_id, date
        ),

        all_lines AS (
            SELECT * FROM real_moves
            UNION ALL
            SELECT * FROM missing_months
        ),

        balances AS (
            SELECT
                l.*,
                SUM(l.debit - l.credit) OVER (
                    PARTITION BY company_id, account_id, analytic_account_id
                    ORDER BY date
                ) AS final_balance
            FROM all_lines l
        ),

        final AS (
            SELECT
                *,
                LAG(final_balance, 1, 0) OVER (
                    PARTITION BY company_id, account_id, analytic_account_id
                    ORDER BY date
                ) AS previous_balance
            FROM balances
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
            allss_date,
            allss_previous_balance,
            allss_debit,
            allss_credit,
            allss_final_balance
        )
        SELECT
            row_number() OVER () AS id,
            1, CURRENT_DATE, 1, CURRENT_DATE,
            company_id,
            account_id,
            analytic_account_id,
            date,
            previous_balance,
            debit,
            credit,
            final_balance
        FROM final
        ORDER BY company_id, analytic_account_id, account_id, date;
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
