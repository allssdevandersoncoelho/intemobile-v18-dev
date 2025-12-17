import re
import logging
from odoo import fields, models, api, _, tools
import odoo.addons.decimal_precision as dp
from datetime import date

_logger = logging.getLogger(__name__)

# Date Mask
bdate = re.compile(r'\d{4}\-\d{2}\-\d{2}')

# Domain operators.
NOT_OPERATOR = '!'
OR_OPERATOR = '|'
AND_OPERATOR = '&'
DOMAIN_OPERATORS = (NOT_OPERATOR, OR_OPERATOR, AND_OPERATOR)

# List of available term operators. It is also possible to use the '<>'
# operator, which is strictly the same as '!='; the later should be prefered
# for consistency. This list doesn't contain '<>' as it is simpified to '!='
# by the normalize_operator() function (so later part of the code deals with
# only one representation).
# Internals (i.e. not available to the user) 'inselect' and 'not inselect'
# operators are also used. In this case its right operand has the form (subselect, params).
TERM_OPERATORS = ('=', '!=', '<=', '<', '>', '>=', '=?', '=like', '=ilike',
                  'like', 'not like', 'ilike', 'not ilike', 'in', 'not in',
                  'child_of', 'parent_of')

# A subset of the above operators, with a 'negative' semantic. When the
# expressions 'in NEGATIVE_TERM_OPERATORS' or 'not in NEGATIVE_TERM_OPERATORS' are used in the code
# below, this doesn't necessarily mean that any of those NEGATIVE_TERM_OPERATORS is
# legal in the processed term.
NEGATIVE_TERM_OPERATORS = ('!=', 'not like', 'not ilike', 'not in')

# Negation of domain expressions
DOMAIN_OPERATORS_NEGATION = {
    AND_OPERATOR: OR_OPERATOR,
    OR_OPERATOR: AND_OPERATOR,
}
TERM_OPERATORS_NEGATION = {
    '<': '>=',
    '>': '<=',
    '<=': '>',
    '>=': '<',
    '=': '!=',
    '!=': '=',
    'in': 'not in',
    'like': 'not like',
    'ilike': 'not ilike',
    'not in': 'in',
    'not like': 'like',
    'not ilike': 'ilike',
}

TRUE_LEAF = (1, '=', 1)
FALSE_LEAF = (0, '=', 1)

TRUE_DOMAIN = [TRUE_LEAF]
FALSE_DOMAIN = [FALSE_LEAF]


class BalanceAccountStructure(models.Model):
    _name = "allss.balance.account.structure"
    _description = "Balancete Estruturado"
    _order = "allss_company_id, allss_account_id, allss_date"

    allss_company_id = fields.Many2one('res.company', string='Empresa', store=True, index=True)

    allss_parent_id_6 = fields.Many2one('account.group', string='1º Nível', store=True, index=True)
    allss_parent_id_5 = fields.Many2one('account.group', string='2º Nível', store=True, index=True)
    allss_parent_id_4 = fields.Many2one('account.group', string='3º Nível', store=True, index=True)
    allss_parent_id_3 = fields.Many2one('account.group', string='4º Nível', store=True, index=True)
    allss_group_id = fields.Many2one('account.group', string='5º Nível', store=True, index=True)

    allss_account_id = fields.Many2one('account.account', string='Conta', store=True, index=True)

    allss_date = fields.Date("Data", store=True, index=True)

    allss_previous_balance = fields.Float("Saldo Anterior", store=True, index=True, digits=dp.get_precision('Account Balance'))
    allss_debit = fields.Float("Débito", store=True, index=True, digits=dp.get_precision('Account Balance'))
    allss_credit = fields.Float("Crédito", store=True, index=True, digits=dp.get_precision('Account Balance'))
    allss_final_balance = fields.Float("Saldo Atual", store=True, index=True, digits=dp.get_precision('Account Balance'))

    

    # @api.model
    # def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
    #     fields_list = [
    #         'allss_previous_balance',
    #         'allss_debit',
    #         'allss_credit',
    #         'allss_final_balance',
    #     ]

    #     result = super().read_group(
    #         domain=domain,
    #         fields=fields_list,
    #         groupby=groupby,
    #         offset=offset,
    #         limit=limit,
    #         orderby=orderby,
    #         lazy=lazy,
    #     )

    #     if not result or not fields:
    #         return result

    #     for group_line in result:
    #         group_domain = group_line.get('__domain')
    #         if not group_domain:
    #             continue

    #         # Registro mais antigo do grupo
    #         first_record = self.search(
    #             group_domain,
    #             order='allss_date asc, id asc',
    #             limit=1
    #         )

    #         previous = first_record.allss_previous_balance if first_record else 0.0

    #         group_line['allss_previous_balance'] = previous
    #         group_line['allss_final_balance'] = (
    #             previous
    #             + group_line.get('allss_debit', 0.0)
    #             - group_line.get('allss_credit', 0.0)
    #         )

    #     return result


    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        fields_list = [
            'allss_previous_balance',
            'allss_debit',
            'allss_credit',
            'allss_final_balance',
        ]

        result = super().read_group(
            domain=domain,
            fields=fields_list,
            groupby=groupby,
            offset=offset,
            limit=limit,
            orderby=orderby,
            lazy=lazy,
        )

        if not result or not fields:
            return result

        # 🔹 Coleta todos os domínios de grupo
        group_domains = [
            group['__domain']
            for group in result
            if group.get('__domain')
        ]

        if not group_domains:
            return result

        # 🔹 Constrói um domínio OR gigante (dom1 OR dom2 OR dom3 ...)
        if len(group_domains) == 1:
            big_domain = group_domains[0]
        else:
            big_domain = ['|'] * (len(group_domains) - 1)
            for dom in group_domains:
                big_domain += dom

        # 🔹 Busca tudo de uma vez, já ordenado
        records = self.search(
            big_domain,
            order='allss_company_id, allss_account_id, allss_date asc, id asc'
        )

        # 🔹 Guarda o primeiro saldo por combinação relevante
        first_balance_map = {}

        for rec in records:
            key = (
                rec.allss_company_id.id if rec.allss_company_id else None,
                rec.allss_account_id.id if rec.allss_account_id else None,
                rec.allss_parent_id_6.id if rec.allss_parent_id_6 else None,
                rec.allss_parent_id_5.id if rec.allss_parent_id_5 else None,
                rec.allss_parent_id_4.id if rec.allss_parent_id_4 else None,
                rec.allss_parent_id_3.id if rec.allss_parent_id_3 else None,
                rec.allss_group_id.id if rec.allss_group_id else None,
            )

            # só o primeiro registro do grupo interessa
            if key not in first_balance_map:
                first_balance_map[key] = rec.allss_previous_balance or 0.0

        # 🔹 Aplica os valores calculados
        for group_line in result:
            key = (
                group_line.get('allss_company_id'),
                group_line.get('allss_account_id'),
                group_line.get('allss_parent_id_6'),
                group_line.get('allss_parent_id_5'),
                group_line.get('allss_parent_id_4'),
                group_line.get('allss_parent_id_3'),
                group_line.get('allss_group_id'),
            )

            previous = first_balance_map.get(key, 0.0)

            group_line['allss_previous_balance'] = previous
            group_line['allss_final_balance'] = (
                previous
                + group_line.get('allss_debit', 0.0)
                - group_line.get('allss_credit', 0.0)
            )

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


    

    def init_account_structure(self):
        # Busca todas as combinações de company, account e grupos para o mês atual
        self._cr.execute("""
            SELECT DISTINCT 
                mov.company_id,
                mov.account_id,
                date_trunc('month', gs)::date AS allss_date,
                mov._allss_group_id,
                mov._allss_parent_id_6,
                mov._allss_parent_id_5,
                mov._allss_parent_id_4,
                mov._allss_parent_id_3
            FROM (
                SELECT company_id, account_id, MIN(date) AS date,
                    _allss_group_id, _allss_parent_id_6, _allss_parent_id_5,
                    _allss_parent_id_4, _allss_parent_id_3
                FROM account_move_line
                GROUP BY company_id, account_id, _allss_group_id, _allss_parent_id_6,
                        _allss_parent_id_5, _allss_parent_id_4, _allss_parent_id_3
            ) mov
            INNER JOIN generate_series(
                (SELECT MIN(date) FROM account_move_line),
                CURRENT_DATE + INTERVAL '31 days',
                INTERVAL '1 month'
            ) gs ON gs >= mov.date
            WHERE DATE_PART('month', gs) = DATE_PART('month', CURRENT_DATE)
            AND DATE_PART('year', gs) = DATE_PART('year', CURRENT_DATE)
        """)

        for row in self._cr.fetchall():
            company_id, account_id, allss_date, group_id, p6, p5, p4, p3 = row

            # Verifica se já existe registro
            result = self.env['allss.balance.account.structure'].search([
                ("allss_company_id", '=', company_id),
                ("allss_account_id", '=', account_id),
                ("allss_date", '=', allss_date)
            ], order='allss_company_id, allss_account_id, allss_date')

            if not result:
                # Busca saldo anterior
                res = self.env['allss.balance.account.structure'].search([
                    ("allss_company_id", '=', company_id),
                    ("allss_account_id", '=', account_id),
                    ("allss_date", '<=', allss_date),
                ], limit=1, order='allss_date desc, id desc')

                data = {
                    'allss_company_id': company_id,
                    'allss_account_id': account_id,
                    'allss_date': allss_date,
                    'allss_debit': 0.0,
                    'allss_credit': 0.0,
                    'allss_group_id': group_id,
                    'allss_parent_id_6': p6,
                    'allss_parent_id_5': p5,
                    'allss_parent_id_4': p4,
                    'allss_parent_id_3': p3,
                    'allss_previous_balance': res.allss_final_balance if res else 0.0,
                    'allss_final_balance': res.allss_final_balance if res else 0.0,
                }

                # Cria registro do balancete do mês atual
                self.env['allss.balance.account.structure'].create(data)
                self.env.cr.commit()

        return True




    #Função para popular a tabela de balancete estruturado 17/12/2025 
    def execute_sql(self):
        cr = self._cr

        cr.execute("TRUNCATE TABLE allss_balance_account_structure RESTART IDENTITY CASCADE;")

        cr.execute("""
            INSERT INTO allss_balance_account_structure (
                create_uid, create_date, write_uid, write_date,
                allss_company_id,
                allss_parent_id_6,
                allss_parent_id_5,
                allss_parent_id_4,
                allss_parent_id_3,
                allss_group_id,
                allss_account_id,
                allss_date,
                allss_previous_balance,
                allss_debit,
                allss_credit,
                allss_final_balance
            )
            SELECT
                1,
                NOW(),
                1,
                NOW(),
                aml.company_id,

                COALESCE(aml._allss_parent_id_6,
                        aml._allss_parent_id_5,
                        aml._allss_parent_id_4,
                        aml._allss_parent_id_3,
                        aml._allss_group_id),

                COALESCE(aml._allss_parent_id_5,
                        aml._allss_parent_id_4,
                        aml._allss_parent_id_3,
                        aml._allss_group_id),

                COALESCE(aml._allss_parent_id_4,
                        aml._allss_parent_id_3,
                        aml._allss_group_id),

                COALESCE(aml._allss_parent_id_3,
                        aml._allss_group_id),

                aml._allss_group_id,

                aml.account_id,
                aml.month_date,

                -- saldo anterior
                COALESCE(
                    SUM(aml.balance) OVER (
                        PARTITION BY aml.company_id, aml.account_id
                        ORDER BY aml.month_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ),
                    0
                ),

                aml.debit,
                aml.credit,

                -- saldo final
                SUM(aml.balance) OVER (
                    PARTITION BY aml.company_id, aml.account_id
                    ORDER BY aml.month_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                )

            FROM (
                SELECT
                    l.company_id,
                    l.account_id,
                    DATE_TRUNC('month', gs)::date AS month_date,
                    SUM(l.debit)  AS debit,
                    SUM(l.credit) AS credit,
                    SUM(l.debit - l.credit) AS balance,

                    l._allss_group_id,
                    l._allss_parent_id_3,
                    l._allss_parent_id_4,
                    l._allss_parent_id_5,
                    l._allss_parent_id_6

                FROM account_move_line l
                JOIN account_move m ON m.id = l.move_id AND m.state = 'posted'
                JOIN generate_series(
                    (SELECT MIN(date) FROM account_move_line),
                    CURRENT_DATE,
                    INTERVAL '1 month'
                ) gs ON gs >= DATE_TRUNC('month', l.date)

                GROUP BY
                    l.company_id,
                    l.account_id,
                    month_date,
                    l._allss_group_id,
                    l._allss_parent_id_3,
                    l._allss_parent_id_4,
                    l._allss_parent_id_5,
                    l._allss_parent_id_6
            ) aml
        """)

        cr.commit()










  

    def update_balance(self):
        for rec in self:
            _logger.warning(f'####################### ATUALIZAR SALDOS #######################')
            rec.env.ref('l10n_br_allss_custom_structured_trial_balance_account_reports.balance_structure_update_data').method_direct_trigger()
            break