import unittest

from calc.db.materials import (
    MaterialSearch,
    combine_material_criteria,
    get_S_div1,
    get_S_div2,
    get_all_materials,
)


class MaterialSearchTests(unittest.TestCase):
    def setUp(self):
        self.search = MaterialSearch()

    def test_count_property_matches_unfiltered_database(self):
        result = self.search.search()

        self.assertEqual(2129, result.count)
        self.assertEqual(result.count, len(result))

    def test_structured_identification_finds_single_specific_material(self):
        criteria = combine_material_criteria(
            "AND",
            MaterialSearch.identification("SA-516", field="Specification", exact=True),
            MaterialSearch.identification("70", field="TypeGrade", exact=True),
            MaterialSearch.identification("K02700", field="AlloyDesignationNumber", exact=True),
        )

        material = self.search.one(criteria=criteria)

        self.assertEqual(177, material["id"])
        self.assertEqual("SA-516", material["spec"])
        self.assertEqual("70", material["grade"])
        self.assertEqual("K02700", material["alloy"])

    def test_text_search_finds_material_group_by_composition(self):
        result = self.search.search("composition:Carbon")

        self.assertGreater(result.count, 0)
        self.assertTrue(all("carbon" in material["comp"].lower() for material in result))

    def test_numeric_criteria_support_comparison_and_tolerance(self):
        criteria = combine_material_criteria(
            "AND",
            MaterialSearch.identification("SA-516", field="Specification", exact=True),
            MaterialSearch.smys(">=", 260),
            MaterialSearch.smus("=", 485, tolerance=0.1),
        )

        result = self.search.search(criteria=criteria)

        self.assertEqual(1, result.count)
        self.assertEqual(177, result.one()["id"])

    def test_text_parser_supports_boolean_operators(self):
        result = self.search.search("spec:SA-516 AND (grade:60 OR grade:70) AND NOT uns:K02100")

        self.assertEqual(1, result.count)
        self.assertEqual("70", result.one()["grade"])

    def test_text_parser_accepts_spaced_numeric_and_quoted_values(self):
        result = self.search.search('spec:SA-516 AND composition:"Carbon steel" AND SMYS >= 260')

        self.assertEqual(1, result.count)
        self.assertEqual(177, result.one()["id"])

    def test_ar_criterion_is_valid_when_database_has_no_ar_values(self):
        result = self.search.search(criteria=MaterialSearch.ar(">=", 20))

        self.assertEqual(0, result.count)

    def test_maximum_allowable_temperature_can_be_used_as_structured_criterion(self):
        result = self.search.search(
            criteria=combine_material_criteria(
                "AND",
                MaterialSearch.identification("SA-516", field="Specification", exact=True),
                MaterialSearch.identification("70", field="TypeGrade", exact=True),
                MaterialSearch.maximum_allowable_temperature(">=", 538),
            )
        )

        material = result.one()
        self.assertEqual(177, material["id"])
        self.assertEqual(538.0, material["MaximumAllowableTemperature"])

    def test_maximum_allowable_temperature_can_be_used_in_text_search(self):
        result = self.search.search("spec:SA-516 AND grade:70 AND MAT >= 538")

        self.assertEqual(1, result.count)
        self.assertEqual(177, result.one()["id"])

    def test_get_all_materials_includes_maximum_allowable_temperature(self):
        material = next(m for m in get_all_materials() if m["id"] == 177)

        self.assertEqual(538.0, material["MaximumAllowableTemperature"])

    def test_free_text_can_identify_class_condition_temper(self):
        result = self.search.search("SA-336 F11 3")

        self.assertEqual(1, result.count)
        material = result.one()
        self.assertEqual("SA-336", material["spec"])
        self.assertEqual("F11", material["grade"])
        self.assertEqual("3", material["cls"])

    def test_asme_allowable_stress_uses_celsius_temperature_breakpoints(self):
        examples = [
            ("SA-336 F11 3", 148.0, 175.0),
            ("SA-336 F22 3", 141.0, 176.0),
        ]

        for query, expected_s1, expected_s2 in examples:
            with self.subTest(query=query):
                material = self.search.search(query).one()

                self.assertEqual(expected_s1, get_S_div1(material["id"], 200.0))
                self.assertEqual(expected_s2, get_S_div2(material["id"], 200.0))


if __name__ == "__main__":
    unittest.main()
