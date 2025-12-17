# -*- coding: utf-8 -*-
# © 2025 ALLSS Soluções em Sistemas LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from lxml import objectify
from odoo import models, fields

class L10nBrAlssWizardNfeImport(models.TransientModel):
    _inherit = 'l10n.br.allss.wizard.nfe.import'
    
    l10n_br_allss_group_id = fields.Many2one('account.group', 'Grupo Contábil', required=False)


    def _l10n_br_allss_import_xml(self, auto, xml):
        nfe = objectify.fromstring(xml)
        obj_account_move = self.env['account.move'].sudo().with_context(l10n_br_allss_group_id=self.l10n_br_allss_group_id).sudo()
        company_id = self.env.company.sudo()

        obj_account_move.import_nfe(
            auto, company_id, nfe, xml, False,
            company_id.l10n_br_allss_partner_automation,
            company_id.l10n_br_allss_invoice_automation, 
            company_id.l10n_br_allss_tax_automation,
            company_id.l10n_br_allss_supplierinfo_automation, 
            fiscal_position_id=company_id.l10n_br_allss_fiscal_position_id_automation or False, 
            account_move_dict=False,
            purchase_order_automation=company_id.l10n_br_allss_purchase_order_automation
        )
        
        return True if obj_account_move else False
