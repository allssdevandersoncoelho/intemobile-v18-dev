from odoo import fields, models, api, _
from datetime import date
from dateutil.relativedelta import relativedelta



class AccountBalanceLineResult(models.Model):
    _name = "allss.balance.line.result"
    _description = "Contas Contábeis e Analíticas"

    allss_balance_calculation_id = fields.Many2one('allss.balance.calculation.result', string='Result', 
                                                store=True, index=True)
    allss_company_id = fields.Many2one('res.company', string='Empresa', store=True, index=True)

    allss_account_id = fields.Many2one('account.account', string='Conta', 
                                                required=True, store=True, index=True)

    allss_account_analytic_id = fields.Many2one('account.analytic.account', string='Conta Analítica', 
                                                store=True, index=True)

    allss_date = fields.Date(string="Data", required=True, store=True, index=True)

    allss_debit = fields.Float(string="Débito", store=True, index=True)
    allss_credit = fields.Float(string="Crédito", store=True, index=True)



class AccountBalanceCalculationResult(models.Model):
    _name = "allss.balance.calculation.result"
    _description = "Apuração de Resultado do Exercício com Contas Analíticas"

    allss_date = fields.Date(string="Data", store=True, required=True, index=True)
    allss_reference = fields.Text(string='Referência', required=True, store=True, index=True)
    allss_account_journal_id = fields.Many2one('account.journal', string='Diário', store=True,
                                                domain="[('type', '=', 'general')]", 
                                                required=True, index=True)
    allss_state = fields.Selection([('draft', 'Unposted'), ('posted', 'Posted'),  ('cancel', 'Cancel')], string='Status',
                            required=True, readonly=True, copy=False, default='draft')
    allss_balance_line_ids = fields.One2many('allss.balance.line.result', 'allss_balance_calculation_id', 
                                            string="Contas Analiticas")


    # @api.model
    # def create(self, vals):
    #     result = super(AccountBalanceCalculationResult, self).create(vals)
    #     result.accounts_action()
    #     return result


    def create(self, vals_list):
        return super().create(vals_list)



     
    def accounts_action(self):
        if self.allss_state == 'draft':
            view_id = self.env.ref("l10n_br_allss_custom_structured_trial_balance_account_reports.allss_account_group_view").id
            return {
                'name': _("Contas Contábeis para Apuração"),
                'view_mode': 'form',
                'view_id': view_id,
                'res_model': 'allss.account.group',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'context': self.id
            }




     
    def action_post(self):
        if self.allss_state == 'draft' and self.allss_account_journal_id and self.allss_balance_line_ids:
            ref = self.allss_reference
            journal = self.allss_account_journal_id
            currency = journal.currency_id or journal.company_id.currency_id

            move = self.env['account.move'].create({
                'name': '/',
                'journal_id': journal.id,
                'company_id': journal.company_id.id,
                'date': self.allss_date,
                'ref': ref,
                'currency_id': currency.id,
                'type': 'entry',
            })
            aml_obj = self.env['account.move.line'].with_context(
                check_move_validity=False)
            for item in self.allss_balance_line_ids:
                if item.allss_debit:
                    debit_aml_dict = {
                        'name': ref,
                        'move_id': move.id,
                        'debit': item.allss_debit,
                        'credit': item.allss_credit,
                        'account_id': item.allss_account_id.id,
                        'analytic_account_id': item.allss_account_analytic_id.id,
                    }
                    aml_obj.create(debit_aml_dict)
                if item.allss_credit:
                    credit_aml_dict = {
                        'name': ref,
                        'move_id': move.id,
                        'debit': item.allss_debit,
                        'credit': item.allss_credit,
                        'account_id': item.allss_account_id.id,
                        'analytic_account_id': item.allss_account_analytic_id.id,
                    }
                    aml_obj.create(credit_aml_dict)

            move.post()
            self.update({'allss_state': 'posted'})

            return move


    #  
    def action_invoice_draft(self):
        self.update({'allss_state': 'draft'})


    @api.onchange('allss_date')
    def onchange_allss_date(self):
        if not self.allss_date:
            year, month, day = str(date.today()).split('-')
            now_date = date(int(year), int(month), int(day))
            now_date = now_date.replace(day=1)
            self.allss_date = (now_date - relativedelta(days=1))

        self.allss_reference = "Apuração de Resultado do Exercício - {}".format(self.allss_date.strftime("%d/%m/%Y"))





