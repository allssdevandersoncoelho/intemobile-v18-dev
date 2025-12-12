
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


# def account_analytic_def(self):
#     conf = self.env['ir.config_parameter'].sudo()

#     # Código da conta analítica configurada
#     account_analytic_code = conf.get_param(
#         'l10n_br_allss_custom_structured_trial_balance_account_reports.account_analytic'
#     )

#     # Se não tiver configuração → retorna None
#     if not account_analytic_code:
#         return [None, None]

#     # Busca a conta analítica
#     analytic = self.env['account.analytic.account'].search([
#         ('code', '=', account_analytic_code)
#     ], limit=1)

#     # Se não existir → retorna None
#     if not analytic:
#         return [None, None]

#     # Retorna IDs válidos (inteiros)
#     return [
#         analytic.id,                      # ID da conta analítica
#         analytic.plan_id.id if analytic.plan_id else None  # ID do plano analítico
#     ]

