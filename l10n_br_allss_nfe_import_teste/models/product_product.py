# -*- coding: utf-8 -*-

from odoo import models


class L10nBrAllssProductProduct(models.Model):
    _inherit = 'product.product'

    def _is_notification_scheduled(self):
        return
