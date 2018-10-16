SELECT subjects_line.id,
subjects_line.nickname, 
subjects_line.name,
subjects_line.description,
subjects_line.target_phenotype,
subjects_line.subject_autoname_index,
subjects_line.breeding_pair_autoname_index,
subjects_line.litter_autoname_index,
subjects_species.nickname AS species,
subjects_strain.name AS strain,
subjects_line.json
FROM subjects_line
LEFT JOIN subjects_species on subjects_line.species_id=subjects_species.id
LEFT JOIN subjects_strain on subjects_line.strain_id=subjects_strain.id
