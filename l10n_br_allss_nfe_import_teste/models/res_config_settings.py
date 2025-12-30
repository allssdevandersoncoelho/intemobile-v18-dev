# -*- coding: utf-8 -*-

from odoo import fields, models


class L10nBrAllssResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_br_allss_product_sequence_id = fields.Many2one(
        'ir.sequence',
        string="Seq. para o produto",
        help="Esta sequência é utilizada apenas na importação de NFe via XML, para a criação automática do produto, sendo utilizado em sua referência interna",
        default=lambda self: (
            self.env.ref(
                "l10n_br_allss_nfe_import_teste.sequence_l10n_br_allss_nfe_import_product",
                raise_if_not_found=False,
            )
            or self.env['ir.sequence'].search(
                [('code', '=', 'l10n_br_allss_nfe_import_teste.product')], limit=1
            )
            or False
        ),
    )
    l10n_br_allss_ms_code_for_nfe_import = fields.Many2one(
        'l10n.br.allss.ms.line', 
        string="ALLSS Service",
        help="Serviço ALLSS para a DF-e e Importação dos arquivos XML da NF-e.")
    l10n_br_allss_nfe_import_nfe_mde_limit_for_process = fields.Integer(
        string="Limite de DF-es para processamento",
        help="Número limite de registros de DF-es para serem processados, visando um estrangulamento no processamento e no tráfego de dados.",
        default=50)

    def get_values(self):
        res = super(L10nBrAllssResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            l10n_br_allss_product_sequence_id=int(params.get_param(
                'l10n_br_allss_nfe_import_teste.l10n_br_allss_product_sequence_id', default=0)),
            l10n_br_allss_ms_code_for_nfe_import=int(params.get_param(
                'l10n_br_allss_nfe_import_teste.l10n_br_allss_ms_code_for_nfe_import', default=0))
            or self.env.get('l10n.br.allss.ms.line'),
            l10n_br_allss_nfe_import_nfe_mde_limit_for_process=int(params.get_param(
                'l10n_br_allss_nfe_import_teste.l10n_br_allss_nfe_import_nfe_mde_limit_for_process', default=50)),
        )
        return res

    def set_values(self):
        super(L10nBrAllssResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'l10n_br_allss_nfe_import_teste.l10n_br_allss_product_sequence_id',
            self.l10n_br_allss_product_sequence_id.id)
        self.env['ir.config_parameter'].sudo().set_param(
            'l10n_br_allss_nfe_import_teste.l10n_br_allss_ms_code_for_nfe_import',
            self.l10n_br_allss_ms_code_for_nfe_import.id)
        self.env['ir.config_parameter'].sudo().set_param(
            'l10n_br_allss_nfe_import_teste.l10n_br_allss_nfe_import_nfe_mde_limit_for_process',
            self.l10n_br_allss_nfe_import_nfe_mde_limit_for_process or 50)
