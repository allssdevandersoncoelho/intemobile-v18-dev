from odoo import models, fields
import logging
_logger = logging.getLogger(__file__)


class StockPickingCustom(models.Model):
    _inherit = 'stock.picking'

    l10n_br_allss_account_move_id = fields.Many2one('account.move', 'Invoice', copy=False)