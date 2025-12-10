
def account_analytic_def(self):
    conf = self.env['ir.config_parameter'].sudo()
    account_analytic_param = conf.get_param('l10n_br_allss_custom_structured_trial_balance_account_reports.account_analytic')

    account_analytic = self.env['account.analytic.account'].search([('code', '=', account_analytic_param)])
    analytic_account_plan = self.env['account.analytic.account'].search([('id', '=', account_analytic.id)])

    if not account_analytic:
        account_analytic_id = '0'
        analytic_account_plan_id = '0'
    else:
        account_analytic_id = account_analytic.id
        analytic_account_plan_id = analytic_account_plan.plan_id.id

    return [account_analytic_id, analytic_account_plan_id]

