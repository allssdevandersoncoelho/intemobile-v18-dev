# -*- coding: utf-8 -*-

from odoo import models
from odoo import fields


class L10nBrAllssNfeXmlPortions(models.Model):
    _name = 'l10n.br.allss.nfe.xml.portions'

    l10n_br_allss_account_move_id = fields.Many2one('account.move', 'Fatura', ondelete='cascade',
                                                    required=True)
    l10n_br_allss_date_maturity = fields.Date('Data de Vencimento')
    l10n_br_allss_price_total = fields.Float('Valor Total')
    l10n_br_allss_amount_currency = fields.Float('Valor Total na Moeda')
    l10n_br_allss_duplicate_number = fields.Char('Parcela')
