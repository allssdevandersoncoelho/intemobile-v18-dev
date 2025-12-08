# © 2020 ALLSS Soluções em Sistemas
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models

class AccountAccount(models.Model):
    _inherit = 'account.account'

    l10n_br_allss_intemobile_name = fields.Char(
        string="Nome SPED Referencial",
        index=True,
        help="Nome da Conta SPED Referencial em Relação ao Código do Plano de Contas "
             "da Intemobile"
    )
    l10n_br_allss_intemobile_code = fields.Char(
        size=64,
        index=True,
        string="Código SPED Referencial",
        help="Número de Conta do SPED Referencial em Relação ao Código do Plano de Contas "
             "da Intemobile"
    )