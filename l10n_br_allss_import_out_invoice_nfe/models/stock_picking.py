from odoo import models, fields


class StockPickingCustom(models.Model):
    _inherit = 'stock.picking'

    l10n_br_allss_account_move_id = fields.Many2one('account.move', 
                                                    string='Invoice', 
                                                    copy=False)
