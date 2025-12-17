# -*- coding: utf-8 -*-
# © 2023 Tiago Prates <tiago.prates@allss.com.br>, ALLSS Soluções em Sistemas LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import logging

_logger = logging.getLogger(__file__)

from os import path
from zipfile import ZipFile
from io import BytesIO
from lxml import objectify
from lxml.etree import XMLSyntaxError

from odoo import api, models, fields
from odoo.exceptions import UserError, RedirectWarning, ValidationError



class L10nBrAlssWizardNfeImport(models.TransientModel):
    _inherit = 'l10n.br.allss.wizard.nfe.import'
    

    l10n_br_allss_group_id = fields.Many2one('account.group', 'Grupo Contábil', required=False)


    def _l10n_br_allss_import_xml(self, auto, xml):
        nfe = objectify.fromstring(xml)
        obj_account_move = (self.env['account.move'].with_context(l10n_br_allss_group_id=self.l10n_br_allss_group_id).sudo())
        company_id = self.env.company.sudo()
        # _logger.warning(f'>>>>> 🟢 obj_account_move: {obj_account_move}')
        # _logger.warning(f'>>>>> 🔴 nfe{nfe} --- xml {xml} ')
        # _logger.warning(f'>>>>>>>>>> ALLSS > _l10n_br_allss_import_xml > company_id ({type(company_id)}): {company_id}')
        # _logger.warning(f'>>>>>>>>>> ALLSS > _l10n_br_allss_import_xml > company_id.l10n_br_allss_fiscal_position_id_automation ({type(company_id.l10n_br_allss_fiscal_position_id_automation )}): {company_id.l10n_br_allss_fiscal_position_id_automation }')

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
        
        if not obj_account_move:
            return False
        else:
            return True