# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError


class L10nBrAllssWizardOperationNotPerformed(models.TransientModel):
    _name = 'l10n.br.allss.wizard.operation.not.perfomed'
    _description = "Motivo da Operacao nao Realizada"

    # l10n_br_allss_nfe_mde_id = fields.Many2one('l10n.br.allss.nfe.mde', string="Documento")
    l10n_br_allss_justification = fields.Text('Justificativa', required=True)

    def l10n_br_allss_action_operation_not_performed(self):
        if len(self.l10n_br_allss_justification) > 15:
            self.env.get('l10n.br.allss.nfe.mde').sudo().browse(self.env.context.get('active_id')). \
                l10n_br_allss_action_not_operation(justification=self.l10n_br_allss_justification)
        else:
            raise UserError("Justificativa deve ter mais de 15 caracteres!")
