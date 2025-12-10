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

    


    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        fields_list = ['allss_previous_balance', 'allss_debit', 'allss_credit', 'allss_final_balance']
        result = super(BalanceAccountStructure, self).read_group(
            domain=domain, fields=fields_list, groupby=groupby, offset=offset,
            limit=limit, orderby=orderby, lazy=lazy)

        if result and fields:
            for group_line in result:
                # Apenas recalcula para grupos, não para linhas únicas
                if "allss_account_id_count" in group_line and group_line["allss_account_id_count"] > 1:
                    # Filtra registros correspondentes ao grupo atual
                    account_id = group_line.get('allss_account_id')
                    company_id = group_line.get('allss_company_id')
                    if account_id and company_id:
                        records = self.search([
                            ('allss_company_id', '=', company_id),
                            ('allss_account_id', '=', account_id)
                        ], order='allss_date asc')
                        previous = records[0].allss_previous_balance if records else 0.0
                        group_line["allss_previous_balance"] = previous
                        group_line["allss_final_balance"] = previous + group_line.get("allss_debit", 0.0) - group_line.get("allss_credit", 0.0)
                else:
                    # Para linhas únicas, mantém os valores calculados
                    group_line["allss_final_balance"] = group_line.get("allss_previous_balance", 0.0) + group_line.get("allss_debit", 0.0) - group_line.get("allss_credit", 0.0)

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



    def execute_sql(self):
        # Limpa a tabela antes de inserir
        self._cr.execute("DELETE FROM public.allss_balance_account_structure;")

        sql = """
        WITH
       
        base_sum AS (
            SELECT
                aml.company_id AS allss_company_id,
                aml.account_id AS allss_account_id,
                aml.date AS allss_date,
                SUM(aml.debit) AS allss_debit,
                SUM(aml.credit) AS allss_credit
            FROM account_move_line aml
            GROUP BY aml.company_id, aml.account_id, aml.date
        ),

      
        mv_sum AS (
            SELECT
                bs.*,
                SUM(bs.allss_debit - bs.allss_credit) OVER (
                    PARTITION BY bs.allss_company_id, bs.allss_account_id
                    ORDER BY bs.allss_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS allss_final_balance
            FROM base_sum bs
        ),

       
        with_prev AS (
            SELECT
                mv.*,
                LAG(allss_final_balance, 1, 0) OVER (
                    PARTITION BY allss_company_id, allss_account_id
                    ORDER BY allss_date
                ) AS allss_previous_balance
            FROM mv_sum mv
        ),

        
        account_groups AS (
            SELECT
                rel.account_account_id,
                rel.allss_account_group_id
            FROM account_account_allss_account_group_rel rel
        )

     
        INSERT INTO public.allss_balance_account_structure (
            allss_company_id,
            allss_account_id,
            allss_group_id,
            allss_parent_id_3,
            allss_parent_id_4,
            allss_parent_id_5,
            allss_parent_id_6,
            allss_date,
            allss_debit,
            allss_credit,
            allss_previous_balance,
            allss_final_balance
        )
        SELECT
            wp.allss_company_id,
            wp.allss_account_id,
            ag.id AS allss_group_id,
            ag3.id AS allss_parent_id_3,
            ag4.id AS allss_parent_id_4,
            ag5.id AS allss_parent_id_5,
            ag6.id AS allss_parent_id_6,
            wp.allss_date,
            wp.allss_debit,
            wp.allss_credit,
            wp.allss_previous_balance,
            wp.allss_final_balance
        FROM with_prev wp
        LEFT JOIN account_groups agr ON agr.account_account_id = wp.allss_account_id
        LEFT JOIN allss_account_group ag ON ag.id = agr.allss_account_group_id
        LEFT JOIN allss_account_group ag3 ON ag3.id = ag.allss_account_bridge_id
        LEFT JOIN allss_account_group ag4 ON ag4.id = ag3.allss_account_bridge_id
        LEFT JOIN allss_account_group ag5 ON ag5.id = ag4.allss_account_bridge_id
        LEFT JOIN allss_account_group ag6 ON ag6.id = ag5.allss_account_bridge_id
        ORDER BY wp.allss_company_id, wp.allss_account_id, wp.allss_date;
        """

        # Executa a query
        self._cr.execute(sql)

        # Atualiza sequência
        self._cr.execute("""
            BEGIN;
                LOCK TABLE allss_balance_account_structure IN EXCLUSIVE MODE;
                SELECT setval(
                    'allss_balance_account_structure_id_seq',
                    COALESCE((SELECT MAX(id)+1 FROM allss_balance_account_structure), 1),
                    false
                );
            COMMIT;
        """)







  

    def update_balance(self):
        for rec in self:
            _logger.warning(f'####################### ATUALIZAR SALDOS #######################')
            rec.env.ref('l10n_br_allss_custom_structured_trial_balance_account_reports.balance_structure_update_data').method_direct_trigger()
            break