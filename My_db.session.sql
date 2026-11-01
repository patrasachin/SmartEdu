select * from student;
select department,count(*)
from student 
group by department;
SELECT department, AVG(marks)
FROM Student
GROUP BY department
HAVING AVG(marks) > 80;

SELECT student_name, marks,
CASE
    WHEN marks >= 90 THEN 'Excellent'
    WHEN marks >= 75 THEN 'Good'
    WHEN marks >= 50 THEN 'Average'
    ELSE 'Fail'
END AS result
FROM Student;
select upper(student_name) from student;
desc student;
alter table student rename column student_id to id;
select name , length(name) as length from student;
select name,department concat(name, ' - ' , department) as concatenation from student;
select * from student;
select substring(name,1,3) as substring from student;
select curdate();
select year(hire_date) from employee;
select * from employee;