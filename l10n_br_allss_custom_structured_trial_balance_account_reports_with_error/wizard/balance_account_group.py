from odoo import fields, models, api, _
from datetime import date
from dateutil.relativedelta import relativedelta
from ..models.allss_funtions import account_analytic_def

class AccountGroupBalance(models.TransientModel):
    _name = "allss.account.group"
    _description = "Contas Contábeis para Apuração"

    def _domain_type_for_allss_account_bridge_id(self):
        unaffected = self.env.ref('account.1_unaffected_earnings_account', raise_if_not_found=False)
        domain = [('internal_group', '=', 'equity')]
        if unaffected:
            domain = ['|', ('id', '=', unaffected.id), ('internal_group', '=', 'equity')]
        search = self.env['account.account'].search(domain).ids

        return f"[('id', 'in', {search})]"
    

    allss_date_de = fields.Date(string="De", required=True, default=fields.Date.context_today)
    allss_date_ate = fields.Date(string="Até", required=True, default=fields.Date.context_today)


    allss_account_bridge_id = fields.Many2one(
        'account.account',
        string='Conta de Apuração',
        domain=_domain_type_for_allss_account_bridge_id,
        required=True,
        store=True,
        index=True
    )

    allss_account_id = fields.Many2many(
        'account.account',
        string='Contas de Resultado a Apurar',
        domain="[('internal_group', 'in', ('income', 'expense'))]",
        required=True,
        store=True,
        index=True
    )


     
    def action_accept(self):
        # print("endtro group")
        # print(self._context)
        active_ids = self.env.context.get('active_ids', [])
        # print(active_ids)
        res_ids = self.env['allss.balance.calculation.result'].search([('id', 'in', active_ids)])

        for res in res_ids:
            account_analytic_id = account_analytic_def(res)[0]
            # print("DADOS depois do For")
            account_ids = str(self.allss_account_id.mapped('id')).strip("[]")
            # print(account_ids)
            self._cr.execute(f""";WITH ULA AS (SELECT DISTINCT allss_account_id as acc_id,
                                                    allss_account_analytic_id as acc_anal, 
			  	                                    MAX(allss_date) as acc_date
			                                    FROM allss_balance_account_analytic
			                                    WHERE allss_date <= '{self.allss_date_ate}'
			                                    AND allss_account_id IN ({account_ids})
			                                    --AND allss_account_analytic_id IN (15, 8)
			                                    --AND allss_final_balance <> 0
			                                    GROUP BY allss_account_id, allss_account_analytic_id
			                                    ORDER BY MAX(allss_date)),
			  
                                ULV AS (SELECT id,
                                            allss_final_balance as acc_final
                                        FROM allss_balance_account_analytic
                                        INNER JOIN ULA ON allss_account_id = ULA.acc_id
                                        AND allss_account_analytic_id = ULA.acc_anal
                                        AND allss_date = UlA.acc_date 
                                        WHERE allss_final_balance <> 0)
                                
                                SELECT allss_acc.id,
                                    allss_acc.allss_company_id,
                                    allss_acc.allss_account_id,
                                    allss_acc.allss_account_analytic_id,
                                    allss_acc.allss_date,
                                    allss_acc.allss_final_balance
                                FROM allss_balance_account_analytic allss_acc
                                INNER JOIN ULV ON ULV.id = allss_acc.id""")

            # print("DEPOIS EXECUTE SQL")
            sql_query = self._cr.fetchall()
            # print(sql_query)
            # print("****************************")

            # print(len(res.allss_balance_line_ids))
            if len(res.allss_balance_line_ids) > 0:
                for line in res.allss_balance_line_ids:
                    # (2, ID) remove and delete the linked record with id = ID (calls unlink on ID, that will
                    # delete the object completely, and the link to it as well)
                    res.allss_balance_line_ids = [(2, line.id)]
            value = {}
            # print("ANTES DO FOR ROW")
            # print(sql_query)
            # print("***********************")
            for row in sql_query:
                # print(row)
                if row[5] < 0:
                    allss_debit = (row[5] * -1)
                    allss_credit = 0
                else:
                    allss_debit = 0
                    allss_credit = row[5]

                value['allss_balance_line_ids'] = [(0, False, {'allss_company_id': row[1],
                                                       'allss_account_id': row[2],
                                                       'allss_account_analytic_id': row[3],
                                                       'allss_date': res.allss_date,
                                                       'allss_debit': allss_debit,
                                                       'allss_credit': allss_credit
                                                       })]

                res.write(value)

                value['allss_balance_line_ids'] = [(0, False, {'allss_company_id': row[1],
                                                               'allss_account_id': self.allss_account_bridge_id.id,
                                                               'allss_account_analytic_id': row[3],
                                                               'allss_date': res.allss_date,
                                                               'allss_debit': allss_credit,
                                                               'allss_credit': allss_debit
                                                               })]
                res.write(value)

        pass